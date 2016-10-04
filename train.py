import cv2
import os
import fnmatch
import numpy as np
import time
import random

# from pudb import set_trace
from kmajority import kmajority, compute_hamming_hist
from features import get_features_array
from divide import divide_in
from sklearn import neighbors, svm
from sklearn.ensemble import RandomForestClassifier
from sklearn.externals import joblib


def cross_validate_with_participants(kfold, participants, detector_name='SIFT', descriptor_name='SIFT', dect_params=None, model_params=None, n_features=10, bow_size=1000, k=15, classifier="svm", save=False, cream=True):
    overall_start_time = time.time()

    random.seed(0)
    participants_sliced = divide_in(participants, kfold)
    folds = []
    for p in participants_sliced:
        filenames_pos, filenames_neg = filenames_for_participants(p, os.walk("train_set"), cream=cream)
        filenames_pos.sort()
        filenames_neg.sort()
        folds.append([filenames_pos, filenames_neg])

    if save:
        # train a whole model
        train_set_pos = []
        train_set_neg = []
        for j, f_ in enumerate(folds):
            train_set_pos += f_[0]
            train_set_neg += f_[1]
        print "----- Training a whole model to save -----"
        model, vocabulary = train_model(train_set_pos, train_set_neg, detector_name, descriptor_name, dect_params, n_features, bow_size, k, model_params=model_params, classifier=classifier)
        np.save("vocabulary_model", vocabulary)
        joblib.dump(model, 'model.pkl')
        return 0.

    overall_k = 0
    for i, f in enumerate(folds):
        print "----- Fold: " + str(i)

        train_set_pos = []
        train_set_neg = []
        for j, f_ in enumerate(folds):
            if j == i:
                continue
            train_set_pos += f_[0]
            train_set_neg += f_[1]

        test_filenames = f[0] + f[1]
        random.shuffle(test_filenames)
        print "Testing with " + str(len(f[0])) + " pos " + str(len(f[1])) + " neg"
        print "Training with " + str(len(train_set_pos)) + " pos " + str(len(train_set_neg)) + " neg"

        model, vocabulary = train_model(train_set_pos, train_set_neg, detector_name, descriptor_name, dect_params, n_features, bow_size, k, model_params=model_params, classifier=classifier)

        if model is None:
            return 0.

        predictions, labels, covered = predictions_with_set(f, vocabulary, model, detector_name, descriptor_name, dect_params, n_features)

        # class 1 = negative
        true_neg = np.sum((predictions == 1) & (labels == 1))
        false_neg = np.sum((predictions == 1) & (labels == 0))
        true_pos = np.sum((predictions == 0) & (labels == 0))
        false_pos = np.sum((predictions == 0) & (labels == 1))

        spec = true_neg / float(true_neg + false_pos)
        sens = true_pos / float(true_pos + false_neg)

        # youden = (true_pos / float(true_pos + false_neg)) + (true_neg / float(true_neg + false_pos)) - 1
        exp_mean = spec**1.75 * sens**0.75

        print "TP: " + str(true_pos) + " FP: " + str(false_pos) + " TN " + str(true_neg) + " FN: " + str(false_neg)

        accuracy = (np.sum(np.equal(predictions, labels)) * 1.) / len(test_filenames)
        overall_k += exp_mean * (covered**0.25)  # previous models were trained without exp weight of coverage)
        print "--- kfold: %s, accuracy: %s, exp_mean*coverage: %s" % (str(i), str(accuracy), str(exp_mean * covered))

    print "----- Overall exp mean: " + str(overall_k / float(kfold))
    print("----- Overall kfold took %s ---" % (time.time() - overall_start_time))

    return overall_k / float(kfold)


def filenames_for_participants(participants, directory, cream=True):
    pos = []
    neg = []
    for root, dirnames, filenames in directory:
        for filename in fnmatch.filter(filenames, '*.png'):
            parts = filename.split(" - ")
            subject_id = parts[0]

            if subject_id not in participants:
                continue

            if 'originals' in root:
                continue
            if 'dubious' in root:
                continue
            if '.Apple' in root:
                continue

            if cream:
                if 'cream' in root:
                    pos.append(root + "/" + filename)
                else:
                    neg.append(root + "/" + filename)
            else:
                if 'wart' in root:
                    pos.append(root + "/" + filename)
                if 'neg' in root:
                    neg.append(root + "/" + filename)

    return (pos, neg)


def train_model(train_pos, train_neg, detector_name='SIFT', descriptor_name='SIFT', dect_params=None, n_features=10, bow_size=1000, k=15, model_params=None, classifier="svm"):
    # feat = np.load("f_cache.npy")
    # classes = np.load("c_cache.npy")
    # model = fit_model_svm(feat, classes)

    # return model, np.array([])

    overall_start_time = time.time()

    print("--- Gather features---")
    pos_feat_p_img, neg_feat_p_img = extract_features([train_pos, train_neg], detector_name, descriptor_name, dect_params, n_features)
    pos_feat = [item for sublist in pos_feat_p_img for item in sublist]
    pos_feat = np.asarray(pos_feat)

    neg_feat = [item for sublist in neg_feat_p_img for item in sublist]
    neg_feat = np.asarray(neg_feat)

    features = np.concatenate((pos_feat, neg_feat))
    np.random.seed(42)
    np.random.shuffle(features)

    print("--- Train BOW---")
    if len(features) == 0:
        return None, None
    vocabulary = train_bagofwords(features, bow_size)

    print("--- Make hists---")
    hists, labels, _ = hist_using_vocabulary([pos_feat_p_img, neg_feat_p_img], vocabulary)

    print("--- Fit model---")
    if classifier == "svm":
        model = fit_model_svm(hists, labels, model_params)
    elif classifier == "forest":
        model = fit_model_forest(hists, labels, model_params)
    else:
        model = fit_model_kneighbors(hists, labels, k)

    print("--- Overall training model took %s ---" % (time.time() - overall_start_time))

    return model, vocabulary


def validate_model(model, val_pos, val_neg, detector_name='SIFT', descriptor_name='SIFT', dect_params=None, n_features=10):
    features = np.concatenate((val_pos, val_neg))
    np.random.seed(21)
    np.random.shuffle(features)


def predictions_with_set(test_set, vocabulary, model, detector_name='SIFT', descriptor_name='SIFT', dect_params=None, n_features=10, norm=cv2.NORM_L2):
    # descs = np.load("des_cache.npy")
    # indices = np.load("indices_cache.npy")
    features = extract_features(test_set, detector_name, descriptor_name, dect_params, n_features)
    descs, _, indices = hist_using_vocabulary(features, vocabulary)

    # np.save("des_cache", descs)
    # np.save("indices_cache", indices)
    predictions = model.predict(descs)

    pred_ind = np.ones(len(test_set[0]) + len(test_set[1]))  # 1 == negative (confusing, i know)

    concat_indices = np.zeros(len(indices[0]) + len(indices[1]))
    concat_indices[0:len(indices[0])] = indices[0]
    concat_indices[len(indices[0]):len(indices[0]) + len(indices[1])] = np.array(indices[1]) + len(test_set[0])
    pred_ind[concat_indices.astype(int)] = predictions

    labels = np.ones(len(test_set[0]) + len(test_set[1]))
    labels[0:len(test_set[0])] = 0

    return pred_ind, labels, len(predictions) / float(len(test_set[0]) + len(test_set[1]))


def classify_img_using_model(img_filename, vocabulary, model, detector_name='SIFT', descriptor_name='SIFT', dect_params=None, n_features=10, norm=cv2.NORM_L2):
    return predictions_with_set([img_filename], vocabulary, model, detector_name, descriptor_name, dect_params, n_features, norm)[0]


def extract_features(classes, detector_name, descriptor_name, dect_params, n_features):
    features_per_class = []
    for c in classes:
        features = get_features_array(c, detector_name, descriptor_name, dect_params, max_features=n_features)
        features_per_class.append(features)
    return features_per_class


def train_bagofwords(features, bow_size, norm=cv2.NORM_L2):
    if norm == cv2.NORM_L2:
        bow = cv2.BOWKMeansTrainer(bow_size)
        bow.add(features)
        vocabulary = bow.cluster()

    else:
        # implementation of https://www.researchgate.net/publication/236010493_A_Fast_Approach_for_Integrating_ORB_Descriptors_in_the_Bag_of_Words_Model
        vocabulary = kmajority(features.astype(int), bow_size)

    return vocabulary


def hist_with_img(descs, vocabulary, norm=cv2.NORM_L2):
    if norm == cv2.NORM_L2:
        hist = np.zeros(len(vocabulary))

        for desc in descs:
            match = np.sum(np.square(np.abs(vocabulary - desc)),1).argmin()
            hist[match] += 1

        hist /= len(descs)
        hist = hist.astype(np.float32)

    else:
        hist = compute_hamming_hist(descs, vocabulary)

    return hist


def hist_using_vocabulary(feat_per_img_per_class, vocabulary, norm=cv2.NORM_L2):
    max_count = 0
    for c in feat_per_img_per_class:
        max_count += len(c)

    histograms = np.zeros((max_count, len(vocabulary)), dtype=np.float32)
    labels = np.zeros(max_count)
    indices = []

    i = 0
    no_feat_counter = 0
    for label, wart_imgs in enumerate(feat_per_img_per_class):
        for j, descs in enumerate(wart_imgs):
            if descs is None or len(descs) == 0:
                no_feat_counter += 1
                continue

            hist = hist_with_img(descs, vocabulary, norm)

            if np.sum(hist) == 0:  # this shouldn't happen... histogram always sums to 1 (except when no match)
                print "[Error] hist == 0 no kps for " + str(filename) + "--- \n"
                continue

            histograms[i] = hist
            labels[i] = label

            if len(indices) < label + 1:
                indices.append([])
            indices[label].append(j)

            i += 1

    if no_feat_counter > 0:
        print "--- No histograms for %s images ---" % str(no_feat_counter)

    return (histograms[0:i], labels[0:i], indices)


def fit_model_kneighbors(feat, classes, k, weights='uniform'):
    clf = neighbors.KNeighborsClassifier(k, weights=weights)
    clf.fit(feat, classes)
    return clf


def fit_model_svm(feat, classes, model_params):
    # np.save("f_cache", np.array(feat))
    # np.save("c_cache", classes)
    # C: controls tradeoff between smooth decision boundary and classifying training points correctly
    # gamma: defines how much influence a single training example has

    # C=1, gamma=0.1 gives ~ 77 % acc
    # model_params['class_weight'] = 'balanced'
    model_params['cache_size'] = 2000
    clf = svm.SVC(**model_params)

    # C = 0.7 gives 0.41 accuracy -.-

    # clf.fit(feat, classes, class_weight={"1": 1.5}, cache_size=7000)  # negative is more important, play with class_weight?
    clf.fit(feat, classes)

    # Proper choice of C and gamma is critical to the SVMs performance.
    # One is advised to use sklearn.grid_search.GridSearchCV with C and gamma spaced exponentially far apart to choose good values.

    return clf


def fit_model_forest(feat, classes, model_params={}):
    clf = RandomForestClassifier(**model_params)
    clf.fit(feat, classes)
    return clf


if __name__ == '__main__':
    parts = []
    for root, dirnames, filenames in os.walk("train_set"):
        for filename in fnmatch.filter(filenames, '*.png'):
            part = filename.split(" - ")[0]
            if part not in parts:
                parts.append(part)

    params = {'nfeatures': 60, 'bow_size': 1013, 'svm_gamma': 1.7507582, 'edgeThreshold': 50., 'svm_C': 0.47862167, 'sigma': 2.25901868, 'contrastThreshold': 0.001}
    params = {'nfeatures': 33, 'bow_size': 972, 'svm_gamma': 0.23088591, 'edgeThreshold': 50., 'svm_C': -0.75793766, 'sigma': 0.82779888, 'contrastThreshold': 0.001}
    params = {'nfeatures': 50, 'bow_size': 1500, 'svm_gamma': -1.27693612, 'edgeThreshold': 50., 'svm_C': 2.78474086, 'sigma': 0.88662046, 'contrastThreshold': 0.001}
    params = {'nfeatures': 84, 'bow_size': 262, 'svm_gamma': -0.105758443512, 'edgeThreshold': 88.4141769336, 'svm_C': 2.83142990871, 'sigma': 0.466832044073, 'contrastThreshold': 0.0001}
    parts.sort()
    dect_params = {
        "nfeatures": params['nfeatures'],
        "contrastThreshold": params['contrastThreshold'],
        "edgeThreshold": params['edgeThreshold'],
        "sigma": params['sigma']
    }
    model_params = {
        "C": 10.**params['svm_C'],
        "gamma": 10.**params['svm_gamma']
    }

    kappa = cross_validate_with_participants(5, parts, dect_params=dect_params, bow_size=params['bow_size'], model_params=model_params, save=True)
