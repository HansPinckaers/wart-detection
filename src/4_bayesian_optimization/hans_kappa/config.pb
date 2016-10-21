language: PYTHON
name:     "experiment" 

variable {
	name: "svm_C"
	type: FLOAT
	size: 1
	min:  -4
	max:  5
}

variable {
	name: "svm_gamma"
	type: FLOAT
	size: 1
	min:  -4
	max:  5
}

variable {
	name: "bow_size"
	type: INT
	size: 1
	min:  250
	max:  3000
}

variable {
	name: "nfeatures"
	type: INT
	size: 1
	min:  10
	max:  100
}

variable {
	name: "contrastThreshold"
	type: FLOAT
	size: 1
	min:  0.001
	max:  0.1
}

variable {
	name: "edgeThreshold"
	type: FLOAT
	size: 1
	min:  3
	max:  50
}

variable {
	name: "sigma"
	type: FLOAT
	size: 1
	min:  0.02
	max:  2 
}