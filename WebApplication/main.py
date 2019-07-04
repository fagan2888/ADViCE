from flask import Flask
from flask import request, jsonify, json, redirect
from flask import render_template
import pandas as pd
import numpy as np

from model import *
from utils import *
from individual_explanation import *
from global_explanations import *
from d3_functions import *
from preprocessing import create_summary_file
from distance_function import generate_projection_files

from os import path



np.random.seed(12345)


""" 
---- Tool Requirements ----

-- Data--
Binary Classification
Maximum 50 Features
First Row Header w/ Names
Last Column Target



"""


# ============= Initialize model =========== #

# --- Setting random seed -- 
np.random.seed(150)



# --- Parameters --- 
data_path = "diabetes.csv"
# data_path = "/static/data/diabetes.csv"
no_bins = 10
preproc_path = "diabetes_preproc.csv"

projection_changes_path = "changes_proj.csv"
projection_anchs_path = "anchs_proj.csv"

model_path = "TBD"   # Manual? 



# --- Advanced Parameters
density_fineness = 1000
categorical_cols = []  # Categorical columns can be customized # Whether there is order
monotonicity_arr = []  # Local test of monotonisity



df = pd.read_csv(data_path)
feature_names = np.array(df.columns)[:-1]
all_data = np.array(df.values)


# -- Split data and target values --
data = all_data[:,:-1]
target = all_data[:,-1]

no_samples, no_features = data.shape


# --- Initialize and train model ---
svm_model = SVM_model(data,target)
svm_model.train_model(0.001)
svm_model.test_model()

bins_centred, X_pos_array, init_vals = divide_data_bins(data,no_bins)  # Note: Does not account for categorical features

density_fineness = 1000
all_den, all_median, all_mean = all_kernel_densities(data,feature_names,density_fineness) # Pre-load density distributions

dict_array = all_den
dict_array_orig = all_den


# --- Perform Preprocessing if new data --- 
if not path.exists(preproc_path): 
	create_summary_file(data, target, svm_model, bins_centred, X_pos_array, init_vals, no_bins, monotonicity_arr, preproc_path)



generate_projection_files(preproc_path, data, target, projection_changes_path, projection_anchs_path) 


# ------- Initialize WebApp ------- #

app = Flask(__name__) # static_folder="C:/Users/Oscar/Documents/UGR 2018/Fico-Challenge-master/VisualApp1/static")

@app.route('/')
def hello():
    return redirect("/intro")

@app.route('/intro')
def intro_site():
	return render_template("index_intro.html")



# ------- Individual Explanations ------- #

@app.route('/individual')
def ind_site():
    return render_template("index_individual.html")

@app.route('/instance', methods=['GET'])
def handle_request():

	np.random.seed(12345)

	if request.method == 'GET':
		sample = -10
		try:
			sample = int(request.args.get('sample'))
		except:
			return "Please enter a sample number in the range (1, "+ str(no_samples) + ")."

		if sample != -10:
			if sample<1 or sample>no_samples:
				return "Please enter a sample number in the range (1, "+ str(no_samples) + ")."
			else:			
				
				monot = (request.args.get('monot') == "True")
				sort = (request.args.get('sort') == "True")
				sample, good_percent, model_correct, category, predicted = display_data(data,target,svm_model,sample)
				
				### Run MSC and Anchors
				change_vector, change_row, anchors, percent = instance_explanation(svm_model, data, data[sample], sample, X_pos_array, bins_centred, 
																no_bins, monotonicity_arr)

				### Parse values into python dictionary
				ret_string = ""
				data_array = prepare_for_D3(data[sample], bins_centred, change_row, change_vector, anchors, percent, feature_names, monot, monotonicity_arr)

				dict_array = []
				if monot:
					dict_array = dict_array_monot
				else:
					dict_array = dict_array_orig

				if sort:
					data_array, dict_array = sort_by_val(data_array, dict_array)

				for dct in data_array:
					ret_string += json.dumps(dct)
					ret_string += "~"

				for dct in dict_array:
					ret_string += json.dumps(dct)
					ret_string += "~"

				
				# text_exp = generate_text_explanation(good_percent, X[sample], change_row, change_vector , anchors)
				similar_ids = detect_similarities("static/data/pred_data_x.csv","static/data/final_data_file.csv", data[sample], change_row, bins_centred, good_percent)
				similar_ids = similar_ids[:min(len(similar_ids),10)]
				ret_string += json.dumps({'sample': sample+1, 'good_percent': good_percent, 'model_correct': model_correct,
										  'category': category, 'predicted': predicted,
										  'similar_ids': similar_ids})
				
				return ret_string



# ------- Global Explanations ------- #

@app.route('/glob_req')
def glob_site_bars():

	if request.method == 'GET':

		ret_arr = []
		arr = list (count_total)
		for item in arr:
			new_item = list(item)
			ret_arr.append(new_item)

		keyTots = []
		chgTots = []
		for i in range(no_features):
			keyTots.append(ret_arr[i][0]+ret_arr[i][1])
			chgTots.append(ret_arr[i][2]+ret_arr[i][3])


		keySort = sorted(range(len(keyTots)), key=lambda k: keyTots[k])[::-1]
		chgSort = sorted(range(len(chgTots)), key=lambda k: chgTots[k])[::-1]

		ret_arr = [keySort, chgSort, ret_arr]

		ret_string = json.dumps(ret_arr)

	return ret_string

@app.route('/global')
def glob_site():
	return render_template("index_global.html")

@app.route('/glob_feat', methods=['GET'])
def handle_request_mini_graphs():

	if request.method == 'GET':

		id_list = request.args.get('id_list').split(',')

		# Cap number of minigraphs on right panel
		sample_cap = min(len(id_list), 30)
		id_list = [int(x) for x in id_list][:sample_cap]

		mini_graph_arr = prep_for_D3_global("static/data/pred_data_x.csv","static/data/final_data_file.csv", id_list, bins_centred, X_pos_array, trans_dict)

		## Parse values into python dictionary
		ret_string = [mini_graph_arr, id_list]
		ret_string = json.dumps(ret_string)

		return ret_string

@app.route('/first_panel', methods=['GET'])
def handle_request_ft():

	if request.method == 'GET':

		ft_list = request.args.get('features')
		ft_list = ft_list[1:-1].split(',')

		# False = changes, True = keyfts
		algorithm = (request.args.get('algorithm') == "True")

		if ft_list[0] == -1 or ft_list == ['']:
			return ""
		else:
			ft_list = [int(x) for x in ft_list]
			ft_list.sort()

		combinations = combination_finder("static/data/pred_data_x.csv",ft_list,algorithm)

		ret_arr = []
		if not algorithm:
			for combi in combinations[:min(15,len(combinations))]:
				ret_arr.append(changes_generator("static/data/pred_data_x.csv", combi))
		else:
			for combi in combinations[:min(15,len(combinations))]:
				ret_arr.append(anchor_generator("static/data/pred_data_x.csv","static/data/final_data_file.csv", combi))


		## Parse values into python dictionary
		ret_string = json.dumps(ret_arr)
		return ret_string



# ------- New Projection ------- #

@app.route('/projection')
def projection_site():
	show_projection(False, list(range(X.shape[0])), "PCA", True)
	return render_template("index_projection.html")

@app.route('/bokeh_req', methods=['GET'])
def bokeh_request_ft():

	if request.method == 'GET':

		ft_list = request.args.get('features')
		ft_list = ft_list[1:-1].split(',')

		# False = changes, True = keyfts
		algorithm = (request.args.get('algorithm') == "True")
		dim_red = request.args.get('dim_red')
		directionality = (request.args.get('directionality') == "True")

		if ft_list[0] == '-1' or ft_list == ['']:
			ret_arr = list(range(X.shape[0]))

		else:
			ft_list = [int(x) for x in ft_list]
			ft_list.sort()
			ret_arr = ids_with_combination("static/data/pred_data_x.csv",ft_list,algorithm)

		# print(ret_arr)
		show_projection(algorithm, ret_arr, dim_red, directionality)

		## Parse values into python dictionary
		ret_string = json.dumps(ret_arr)
		return ret_string

# @app.route('/aggregation_req')
# def projection_site_req():

# 	if request.method == 'GET':

# 		proj_samples = request.args.get('id_list').split(',')

# 		if (proj_samples[0]=='' or proj_samples[0]=='-1'):
# 			return "-1"
			
# 		else:	
# 			# sample_cap = min(len(proj_samples), 30)
# 			proj_samples = [int(x) for x in proj_samples]#[:sample_cap]
# 			proj_arr = prep_for_D3_aggregation("static/data/pred_data_x.csv","static/data/final_data_file.csv", proj_samples, bins_centred, X_pos_array, trans_dict)
# 			ret_string = json.dumps(proj_arr)
# 			return ret_string

@app.route('/violin_req')
def violin_site_req():

	if request.method == 'GET':

		proj_samples = request.args.get('id_list').split(',')

		if (proj_samples[0]=='' or proj_samples[0]=='-1'):
			return "-1"

		else:
			# --- Sort Features ---
			sort_toggle = False

			# sample_cap = min(len(proj_samples), 30)
			proj_samples = np.array([int(x) for x in proj_samples])#[:sample_cap])
			# violin_arr = populate_violin_plot(X_pos_array, proj_samples, trans_dict)
			select_den, select_median, select_mean = specific_kernel_densities(X_no_9, proj_samples, trans_dict)
			# all_den, select_den, all_median , select_median = kernel_density(X_no_9, proj_samples, trans_dict)
			# ret_string = json.dumps([np.array(all_den).tolist(), np.array(select_den).tolist(), np.array(all_median).tolist() , np.array(select_median).tolist()])
			aggr_data = prep_for_D3_aggregation("static/data/pred_data_x.csv","static/data/final_data_file.csv", proj_samples, bins_centred, X_pos_array, trans_dict, sort_toggle)
			ret_string = json.dumps([aggr_data, all_den, select_den, all_median , select_median, all_mean, select_mean])
			# ret_string = json.dumps([aggr_data, all_den, select_den, all_median , select_median])
			return ret_string



# ------- Run WebApp ------- #

if __name__ == '__main__':

	np.random.seed(12345)
	app.run(port=5005, host="0.0.0.0", debug=True)
