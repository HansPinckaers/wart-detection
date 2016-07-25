import scipy.cluster.hierarchy as hac
from hierarchical_tweaked import AgglomerativeClusteringTreeMatrix
from sklearn.feature_extraction.image import grid_to_graph
import numpy as np
import cv2


# function to hierarchical cluster image
def segment_hclustering_sklearn(image, image_name):
    small = cv2.resize(image, (0, 0), fx=0.25, fy=0.25)

    gray = cv2.cvtColor(small, cv2.COLOR_LUV2BGR)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    X = np.reshape(gray, (-1, 1))
    connectivity = grid_to_graph(*gray.shape)
    ward = AgglomerativeClusteringTreeMatrix(n_clusters=0, linkage='complete',
                                             connectivity=connectivity, compute_full_tree=True)
    ward.fit(X)

    linkage_matrix = np.column_stack((ward.children_, ward.distance, ward.n_desc))
    max_distance = np.amax(ward.distance)
    clusters = hac.fcluster(linkage_matrix, max_distance * 0.5, 'distance')
    n_clusters = len(np.unique(clusters))
    # clusters = ward.labels_
    # n_clusters = 2
    label = np.reshape(clusters, gray.shape)

    # Plot the results on an image
    label = np.repeat(np.repeat(label, 4, axis=0), 4, axis=1)
    clusters = []
    
    for l in range(n_clusters):
        # cluster_img = image.copy()
        # cluster_img = cv2.cvtColor(cluster_img, cv2.COLOR_HSV2BGR)
        i_of_cluster = l + 1  # first cluster (0) has label 1
        cluster = np.zeros(image.shape[:2])
        cluster[label == i_of_cluster] = 1
        # cluster_img[label != i_of_cluster] = 0
        # cv2.imshow(image_name + str(l) + "cluster", cluster_img)
        clusters.append(cluster)

    # maybe eliminate spatial regions containing less than minimum amount of pixels
    return clusters


def get_possible_finger_clusters(clusters, image_BGR, image_name):
    img_hsv = cv2.cvtColor(image_BGR, cv2.COLOR_BGR2HSV)

    # D. Chai, and K.N. Ngan, "Face segmentation using skin-color map in videophone applications". IEEE Trans. on Circuits and Systems for Video Technology, 9(4): 551-564, June 1999.
    # skin_ycrcb_mint = np.array((0, 133, 77))
    # skin_ycrcb_maxt = np.array((255, 173, 127))
    # skin_mask = cv2.inRange(img_ycrcb, skin_ycrcb_mint, skin_ycrcb_maxt)
    # cv2.imshow("ycr mask", skin_mask)
    # total_skin = np.count_nonzero(skin_mask)

    skin_color = [8, 176, 187]  # constant
    skin_clusters = []

    pinkest = 0
    lowest_level = 999

    for i, cluster in enumerate(clusters):
        # get average color
        size = np.count_nonzero(cluster)
        if size < img_hsv.shape[0] * img_hsv.shape[1] * 0.2:
            continue

        colors_i = np.nonzero(cluster)
        colors = img_hsv[colors_i]

        average_color = np.mean(colors, axis=0)
        if average_color[0] > 90:
            average_color[0] = 180 - average_color[0]

        dist_to_skin_color = np.linalg.norm(average_color - skin_color)

        if dist_to_skin_color < lowest_level:
            pinkest = i
            lowest_level = dist_to_skin_color

    skin_clusters.append(clusters[pinkest])
    return skin_clusters


def equalizeHistWithMask(src, mask):
    hist_sz = 256
    hist = np.zeros(256)

    for y in range(src.shape[0]):
        for x in range(src.shape[1]):
            if (y < len(mask) and x < len(mask[y]) and mask[y][x]):
                hist[src[y][x]] += 1

    scale = 255. / (np.count_nonzero(mask))
    sum = 0
    lut = np.zeros(257)

    for i in range(hist_sz):
        sum += hist[i]
        val = np.round(sum * scale)
        lut[i] = np.uint8(val)

    lut[0] = 0
    dst = np.zeros(src.shape)

    for y in range(src.shape[0]):
        for x in range(src.shape[1]):
            if (y < len(mask) and x < len(mask[y]) and mask[y][x]):
                dst[y][x] = lut[src[y][x]]

    dst = np.uint8(dst)
    return dst
