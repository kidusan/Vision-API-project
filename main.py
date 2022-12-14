import json
import requests
from flask import Flask, render_template, request
from flask_cors import CORS
from google.cloud import vision_v1
import gcsfs
import google.cloud.storage as storage
from werkzeug.utils import secure_filename
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="privateKey.json"

desc_dict = {}

ALLOWED_EXTENSIONS = set(['jpg','png','jpeg'])
app = Flask(__name__)
CORS(app) 
API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
headers = {"Authorization": f"Bearer {'{insert key here}'}"}

@app.route('/')
def res():
   return render_template('home.html')

@app.route('/result',methods = ['POST', 'GET'])
def result():
   tags = []
   links = []
   if request.method == 'POST':
      user_input = request.form['impath']
      for key in desc_dict:
         data = {
         "inputs": {
               "source_sentence": user_input,
               "sentences": desc_dict[key]
         }
      }
         response = requests.post(API_URL, headers=headers, json=data).json()
         if max(response) > .80:
            links.append(key)
            tags.append(desc_dict[key])
      url_links = list(map(lambda x: x.replace('gs://', 'https://storage.cloud.google.com/'), links))
      return render_template("result.html", links=url_links, tags=tags)      
      
@app.route('/upload',methods = ['POST', 'GET'])
def func():
   files = []
   if request.method == 'POST':   
      if not request.files:
         abort('No fiiile part')         
      #read files   
      files = request.files.getlist('files', None)
      storage_client = storage.Client()
      bucket = storage_client.get_bucket("{your bucket name}") 
      #save files
      for i in range(0, len(files)):
         file = files[i]
         if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            blob = bucket.blob(f'{i}.jpg')
            blob.upload_from_string(
            file.read(),
            content_type=file.content_type
         )
      #analyze files   
      
      for i in range(0, len(files)):
         gcs_file_system = gcsfs.GCSFileSystem(project="{your project name}")
         input_image_uri="{your bucket name}" + str(i) + ".jpg"
         output_uri="{your bucket name/Output}" + str(i) 
         gcs_json_path=output_uri + "output-1-to-1.json"
         sample_async_batch_annotate_images(input_image_uri, output_uri)

         with gcs_file_system.open(gcs_json_path) as f:
            data  = json.load(f)
            for res in data['responses']:
                  for label in res['labelAnnotations']:
                     if input_image_uri not in desc_dict:
                        desc_dict[input_image_uri] = [label['description']]
                     else:
                        desc_dict[input_image_uri].append(label['description'])
         
      return render_template("home.html")
   
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1] in ALLOWED_EXTENSIONS


def sample_async_batch_annotate_images(input_image_uri, output_uri):
    """Perform async batch image annotation."""
    client = vision_v1.ImageAnnotatorClient()

    source = {"image_uri": input_image_uri}
    image = {"source": source}
    features = [
        {"type_": vision_v1.Feature.Type.LABEL_DETECTION},
    ]

    # Each requests element corresponds to a single image.  To annotate more
    # images, create a request element for each image and add it to
    # the array of requests
    requests = [{"image": image, "features": features}]
    gcs_destination = {"uri": output_uri}

    # The max number of responses to output in each JSON file
    batch_size = 100
    output_config = {"gcs_destination": gcs_destination,
                     "batch_size": batch_size}

    operation = client.async_batch_annotate_images(requests=requests, output_config=output_config)

    print("Waiting for operation to complete...")
    response = operation.result(90)
    print(response)
    #print(response.output_config.gcs_destination.uri)
    # The output is written to GCS with the provided output_uri as prefix
    gcs_output_uri = response.output_config.gcs_destination.uri
    #print("Output written to GCS with prefix: {}".format(gcs_output_uri))



if __name__ == '__main__':
   app.run(debug = True)