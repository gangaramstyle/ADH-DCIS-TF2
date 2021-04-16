import os, io
import pydicom
import shutil
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import base64
import pickle
from skimage import exposure
from skimage import morphology
import scipy
import nibabel as nib
from io import BytesIO
import tensorflow as tf

# Flask
from flask import Flask, request, render_template, jsonify, abort
from flask_autoindex import AutoIndex
from gevent.pywsgi import WSGIServer

# SQL
from flask_sqlalchemy import SQLAlchemy

# Declare a flask app
app = Flask(__name__)

AutoIndex(app, browse_root=os.path.curdir+"/static/data/")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)

class Uploads(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    tag = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return '<Result %r>' % self.filename

class Annotations(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(5000), nullable=True)
    annotated = db.Column(db.Boolean, unique=False, default=False)
    tag = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return '<Result %r>' % self.filename

class Results(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(5000), nullable=True)
    result = db.Column(db.String(200), nullable=True)
    tag = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return '<Result %r>' % self.filename
db.create_all()

print('Model loaded. Check http://127.0.0.1:5000/')

table_header = [
    'filename',
    'tag',
    'annotated'
]

upload_base = "/app/uploads/"
mask_base = "static/data/masks/"
image_base = "static/data/images/"
dicom_base = "static/data/dicoms/"
record_base = "static/data/records/"

#TODO: move model outside of static area
model_base = "static/model"

zip_dir = "static/data/zip/"

def make_subdirectories(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)

make_subdirectories(upload_base)
make_subdirectories(mask_base)
make_subdirectories(image_base)
make_subdirectories(dicom_base)
make_subdirectories(record_base)

make_subdirectories(zip_dir)

def delete_folder_contents(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


def get_chunk_name(uploaded_filename, chunk_number):
    return uploaded_filename + "_part_%03d" % chunk_number


def get_chunk_name_finished(uploaded_filename, chunk_number):
    return uploaded_filename + "_part_%03d.finished" % chunk_number


@app.route('/upload', methods=['GET'])
def index():
    # Main page
    uploads = Uploads.query.all()
    return render_template('index.html', results=uploads)

@app.route("/file-exists", methods=['POST'])
def file_exists():
    filename = request.json
    full_file = os.path.join(upload_base, filename)
    return jsonify(os.path.isfile(full_file))

@app.route("/resumable", methods=['GET'])
def resumable():
    resumableIdentfier = request.args.get('resumableIdentifier', type=str)
    resumableFilename = request.args.get('resumableFilename', type=str)
    resumableChunkNumber = request.args.get('resumableChunkNumber', type=int)

    if not resumableIdentfier or not resumableFilename or not resumableChunkNumber:
        # Parameters are missing or invalid
        abort(500, 'Parameter error')

    # chunk folder path based on the parameters
    temp_dir = os.path.join(upload_base, resumableIdentfier)

    # chunk path based on the parameters
    chunk_file = os.path.join(temp_dir, get_chunk_name(
        resumableFilename, resumableChunkNumber))
    app.logger.debug('Getting chunk: %s', chunk_file)

    if os.path.isfile(chunk_file):
        # Let resumable.js know this chunk already exists
        return 'OK'
    else:
        # Let resumable.js know this chunk does not exists and needs to be uploaded
        abort(404, 'Not found')


# if it didn't already upload, resumable.js sends the file here
@app.route("/resumable", methods=['POST'])
def resumable_post():
    resumableTotalChunks = request.form.get('resumableTotalChunks', type=int)
    resumableChunkNumber = request.form.get(
        'resumableChunkNumber', default=1, type=int)
    resumableFilename = request.form.get(
        'resumableFilename', default='error', type=str)
    resumableIdentfier = request.form.get(
        'resumableIdentifier', default='error', type=str)
    tag_text = request.form.get('tag', default='', type=str)

    # get the chunk data
    chunk_data = request.files['file']

    # make our temp directory
    temp_dir = os.path.join(upload_base, resumableIdentfier)
    make_subdirectories(temp_dir)

    # save the chunk data
    chunk_name = get_chunk_name(resumableFilename, resumableChunkNumber)
    chunk_file = os.path.join(temp_dir, chunk_name)
    chunk_data.save(chunk_file)
    chunk_name_finished = get_chunk_name_finished(
        resumableFilename, resumableChunkNumber)
    # TODO: Clean up the chunk finished code
    chunk_finished_file = os.path.join(temp_dir, chunk_name_finished)
    f = open(chunk_finished_file, 'w')
    f.write("\n")
    f.close()

    app.logger.debug('Saved chunk: %s', chunk_file)

    # check if the upload is complete
    chunk_paths = [os.path.join(temp_dir, get_chunk_name(
        resumableFilename, x)) for x in range(1, resumableTotalChunks + 1)]
    chunk_paths_finished = [os.path.join(temp_dir, get_chunk_name_finished(
        resumableFilename, x)) for x in range(1, resumableTotalChunks + 1)]
    upload_complete = all([os.path.exists(p) for p in chunk_paths])
    upload_finished_complete = all(
        [os.path.exists(p) for p in chunk_paths_finished])

    # combine all the chunks to create the final file
    if upload_finished_complete:
        target_file_name = os.path.join(upload_base, resumableFilename)
        with open(target_file_name, "ab") as target_file:
            for p in chunk_paths:
                stored_chunk_file_name = p
                stored_chunk_file = open(stored_chunk_file_name, 'rb')
                target_file.write(stored_chunk_file.read())
                stored_chunk_file.close()
        target_file.close()
        shutil.rmtree(temp_dir)
        app.logger.debug('File saved to: %s', target_file_name)
        upload = Uploads(filename=resumableFilename,  tag=tag_text)
        db.session.add(upload)
        db.session.commit()
        #return that file is fully uploaded
    return 'OK'

@app.route("/delete-file", methods=['POST'])
def delete_file():
    file = request.json
    upload = Uploads.query.filter_by(filename=file).first()
    annotation = Annotations.query.filter_by(filename=file).first()
    result = Results.query.filter_by(filename=file).first()
    db.session.delete(upload)
    db.session.delete(annotation)
    db.session.delete(result)
    db.session.commit()
    return 'OK'

@app.route("/delete-all", methods=['POST'])
def delete_all():
    delete_folder_contents(upload_base)
    delete_folder_contents(mask_base)
    delete_folder_contents(image_base)
    delete_folder_contents(dicom_base)
    delete_folder_contents(record_base)
    Uploads.query.delete()
    Annotations.query.delete()
    Results.query.delete()
    db.session.commit()
    
    return 'OK'

@app.route('/annotate', methods=['GET'])
def annotate():
    # Annotation page
    Annotations.query.delete()
    db.session.commit()

    all_uploads = Uploads.query.all()
    for upload in all_uploads:
        try: #check if the file is a valid dicom
            target_file_name = os.path.join(upload_base, upload.filename)
            dicom = pydicom.dcmread(target_file_name)
            shutil.copy(target_file_name, f"{dicom_base}{upload.filename}")
            annotation = Annotations(filename=upload.filename,  tag=upload.tag)
            db.session.add(annotation)
            db.session.commit()
        except: #not a dicom, so try as a nifti
            try:
                target_file_name = os.path.join(upload_base, upload.filename)
                nifti = nib.load(target_file_name)
                shutil.copy(target_file_name, f"{dicom_base}{upload.filename}")
                annotation = Annotations(filename=upload.filename,  tag=upload.tag)
                db.session.add(annotation)
                db.session.commit()
            except: #neither dicom nor nifti so remove record from db
                pass
                #db.session.delete(upload)
                #db.session.commit()
    dicoms = Annotations.query.all()

    for dicom in dicoms:
        thumbnail, _, _, valid_mask = generateThumbnail(f"{dicom_base}{dicom.filename}", f"{upload_base}{dicom.filename}.mask.pkl")
        if valid_mask:
            shutil.copy(f"{upload_base}{dicom.filename}.mask.pkl", f"{mask_base}{dicom.filename}.mask.pkl")
            dicom.annotated = True
        dicom.thumbnail = thumbnail
        db.session.commit()

    return render_template('annotation.html')


def create_mammo_mask(image, threshold=800, check_mask=False, debug=True):
    """
    :param image: input mammogram
    :param threshold: Pixel value to use for threshold
    :param check_mask: Check mask to make sure it's not fraudulent, i.e. covers > 80% or <10% of the image
        if it is, then use the other mask function
    :return:
    """
    # Create the mask
    mask = np.copy(image)

    # Apply gaussian blur to smooth the image
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    # Threshold the image
    mask = np.squeeze(mask < threshold)

    # Invert mask
    mask = ~mask

    # Morph Dilate to close in bad segs

    # Define the CV2 structuring element
    radius_close = np.round(mask.shape[1] / 45).astype('int16')
    kernel_close = cv2.getStructuringElement(shape=cv2.MORPH_ELLIPSE, ksize=(radius_close, radius_close))

    # Just use morphological closing
    mask = cv2.morphologyEx(mask.astype(np.int16), cv2.MORPH_CLOSE, kernel_close)

    if check_mask:

        # Check if mask is too much or too little
        mask_idx = np.sum(mask) / (image.shape[0] * image.shape[1])

        # If it is, try again
        if mask_idx > 0.8 or mask_idx < 0.1:

            if debug: print('Mask Failed... using method 2')
            del mask
            mask, _ = self.create_breast_mask2(image)


    return mask

def normalize_Mammo_histogram(image, return_values=False, center_type='mean'):
    """
    Uses histogram normalization to normalize mammography data by removing 0 values
    :param image: input volume numpy array
    :param return_values: Whether to return the mean, std and mode values as well
    :param center_type: What to center the data with, 'mean' or 'mode'
    :return:
    """

    # First save a copy of the real image
    img = np.copy(image)

    # First generate a mammo mask then apply it
    mask = create_mammo_mask(image)
    image *= mask.astype(image.dtype)

    # First calculate the most commonly occuring values in the volume
    occurences, values = np.histogram(image, bins=500)

    # Remove 0 values (AIR) which always win
    occurences, values = occurences[1:], values[1:]

    # The mode is the value array at the index of highest occurence
    mode = values[np.argmax(occurences)]

    # Make dummy no zero image array to calculate STD
    dummy, img_temp = [], np.copy(image).flatten()
    for z in range(len(img_temp)):
        if img_temp[z] > 5: dummy.append(img_temp[z])

    # Mean/std is calculated from nonzero values only
    dummy = np.asarray(dummy, np.float32)
    std, mean = np.std(dummy), np.mean(dummy)

    # Now divide the image by the modified STD
    if center_type == 'mode':
        img = img.astype(np.float32) - mode
    else:
        img = img.astype(np.float32) - mean
    img /= std

    # Return values or just volume
    if return_values:
        return img, mean, std, mode
    else:
        return img

def generateThumbnail(image_file, mask=None):
    # returns a base64 encoded thumbnail, 
    # boolean for whether the dicom was valid,
    # and boolean for whether the mask was valid
    valid_dicom = False
    valid_nifti = False
    valid_mask = False
    try:
        img_data = pydicom.dcmread(image_file).pixel_array
        nrm_data = exposure.equalize_adapthist(img_data) * 255
        valid_dicom = True
    except:
        try:
            img_data = np.squeeze(nib.load(image_file).get_data())
            nrm_data = exposure.equalize_adapthist(img_data) * 255
            valid_nifti = True
        except:
            return "", valid_dicom, valid_nifti, valid_mask
    
    try:
        pickleFile = open(mask, 'rb')
        toolstate = pickle.load(pickleFile)
        mask_data = np.zeros_like(img_data)
        for annotation in toolstate:
            points = [(point['x'], point['y']) for point in annotation['handles']['points']]
            points = np.array(points, dtype=np.int32)
            cv2.fillPoly(mask_data,[points],1)
            mask_data[mask_data > 0] = 255
        pickleFile.close()
        valid_mask = True
    except:
        mask_data = np.zeros_like(img_data)
    values = np.nonzero(mask_data)
    masked_channel = np.copy(nrm_data)
    masked_channel[values] = 255
    thumbnail = np.concatenate((masked_channel[...,None], nrm_data[..., None], nrm_data[..., None]), axis=2)
    img = Image.fromarray(thumbnail.astype(np.uint8))
    img = img.resize((40, 40))
    buffered = BytesIO()
    img.save(buffered, format="png")
    img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_b64, valid_dicom, valid_nifti, valid_mask

def resize_to_network(image):
    image = tf.image.resize(image, [128, 128])
    return image

def preprocess(image_file, mask):
    try:
        dcm = pydicom.dcmread(image_file)
        image = dcm.pixel_array
    except:
        nifti =  nib.load(image_file)
        image = np.squeeze(nifti.get_data())
    image = normalize_Mammo_histogram(image)
    pickleFile = open(mask, 'rb')
    toolstate = pickle.load(pickleFile)
    mask_image = np.ascontiguousarray(np.zeros_like(image))

    for annotation in toolstate:
        points = [(point['x'], point['y']) for point in annotation['handles']['points']]
        points = np.array(points, dtype=np.int32)
        cv2.fillPoly(mask_image,[points],1)
        mask_image[mask_image > 0] = 1
    pickleFile.close()
    
    ### find largest blob
    labels = morphology.label(mask_image)
    N = np.bincount(labels.flatten())[1:].argmax() + 1
    blob = (labels == N)
    
    ### find center of largest blob
    cn = scipy.ndimage.center_of_mass(labels)
    center = (int(cn[1]), int(cn[0]))
    
    ### find radius of blob
    radius = int(np.sum(blob)**(1/3)*10)
    
    ### create bounding box
    # assumes that the diameter is never larger than an image axis
    x_start = max(center[0] - radius, 0)
    y_start = max(center[1] - radius, 0)
    if (x_start + 2*radius) > image.shape[1]:
        x_start = image.shape[1] - 2*radius
    if (y_start + 2*radius) > image.shape[0]:
        y_start = image.shape[0] - 2*radius
    x_start = int(x_start)
    y_start = int(y_start)
    bb = image[y_start:y_start + 2*radius, x_start:x_start + 2*radius]

    # TODO: Check 512
    ## rescale box
    box = cv2.resize(bb, (512, 512))
    box = box.reshape(512, 512, 1)

    image_batch = tf.expand_dims(tf.stack(resize_to_network(box)), axis=0)
    loaded_model = tf.keras.models.load_model(model_base)
    return(loaded_model.predict_on_batch(image_batch)['class'][0][1])

@app.route("/save-region-annotation", methods=['POST'])
def save_region_annotation():
    dicom = request.json['dicom']
    toolstate = request.json['toolstate']
    res = Annotations.query.filter_by(filename=dicom).first()
    if toolstate == []:
        if os.path.exists(f"{mask_base}{dicom}.mask.pkl"):
            os.remove(f"{mask_base}{dicom}.mask.pkl")
        thumbnail, _, _, _ = generateThumbnail(f"{dicom_base}{dicom}")
        res.thumbnail = thumbnail
        res.annotated = False
    else:
        outfile = open(f"{mask_base}{dicom}.mask.pkl", 'wb')
        pickle.dump(toolstate, outfile)
        outfile.close()
        thumbnail, _, _, _ = generateThumbnail(f"{dicom_base}{dicom}", f"{mask_base}{dicom}.mask.pkl")
        res.thumbnail = thumbnail
        res.annotated = True
        ###preprocess(f"{dicom_base}{dicom}", f"{mask_base}{dicom}.mask.pkl")
    db.session.commit()
    return 'OK'

@app.route("/get-region-annotation", methods=['POST'])
def get_region_annotation():
    try:
        request.args.get('resumableIdentifier', type=str)
        dicom = request.json['dicom']
        pickleFile = open(f"{mask_base}{dicom}.mask.pkl", 'rb')
        toolstate = pickle.load(pickleFile)
        return jsonify(toolstate)
    except:
        app.logger.debug('No mask found for: %s', dicom)
        return jsonify([])
    
@app.route('/download-dataset', methods=['POST'])
def downloadAnnotatedDataset():
    print("trying to download dataset")
    if request.method == 'POST':
        delete_folder_contents(zip_dir)
        # delete zip
        records = Annotations.query.all()
        for record in records:
            make_subdirectories(f"{zip_dir}{record.tag}/")
            print(f"copying {record.filename}")
            target_dir = f"{zip_dir}{record.tag}/" if record.tag != "" else f"{zip_dir}"
            shutil.copyfile(f"{dicom_base}{record.filename}", f"{target_dir}{record.filename}")
            if record.annotated:
                print(f"copying mask for {record.filename}")
                shutil.copyfile(f"{mask_base}{record.filename}.mask.pkl", f"{target_dir}{record.filename}.mask.pkl")
        shutil.make_archive(f"static/dataset", 'zip', zip_dir)
        return "Success"
    return 'Error'
    # toolstate = request.json['toolstate']
    # outfile = open(f"{raw_base}{dicom}.mask.pkl", 'wb')
    # pickle.dump(toolstate, outfile)
    # outfile.close()
    #res = Results.query.filter_by(filename=dicom).first()
    #print(res)


    # points = np.array([polygon], dtype=np.int32 )
    # img = pydicom.dcmread('/app/data/raw/ser1538img00001.dcm').pixel_array

    # # create mask for polygon
    # mask = np.zeros_like(img)
    # cv2.fillPoly(mask,[points],1)
    # mask[mask > 0] = 255

    # combined = mask * img
    # output = Image.fromarray(combined.astype("uint8"))
    # rawBytes = io.BytesIO()
    # output.save(rawBytes, "JPEG")
    # rawBytes.seek(0)
    # img_base64 = base64.b64encode(rawBytes.read())
    # return jsonify({'status':str(img_base64)})


@app.route('/result', methods=['GET'])
def result():
    # Annotation page
    Results.query.delete()
    db.session.commit()

    dicoms = Annotations.query.all()

    for dicom in dicoms:
        if dicom.annotated == True:
            score = preprocess(f"{dicom_base}{dicom.filename}", f"{mask_base}{dicom.filename}.mask.pkl")
            result = Results(filename=dicom.filename, thumbnail=dicom.thumbnail, result=f'{score*100:.1f}%', tag=dicom.tag)
            db.session.add(result)
            db.session.commit()

    return render_template('results.html')

    # annotated = Annotations.query.all()
    # for upload in all_uploads:
    #     try: #check if the file is a valid dicom
    #         target_file_name = os.path.join(upload_base, upload.filename)
    #         dicom = pydicom.dcmread(target_file_name)
    #         shutil.copy(target_file_name, f"{dicom_base}{upload.filename}")
    #         annotation = Annotations(filename=upload.filename,  tag=upload.tag)
    #         db.session.add(annotation)
    #         db.session.commit()
    #     except: #not a dicom, so try as a nifti
    #         try:
    #             target_file_name = os.path.join(upload_base, upload.filename)
    #             nifti = nib.load(target_file_name)
    #             shutil.copy(target_file_name, f"{dicom_base}{upload.filename}")
    #             annotation = Annotations(filename=upload.filename,  tag=upload.tag)
    #             db.session.add(annotation)
    #             db.session.commit()
    #         except: #neither dicom nor nifti so remove record from db
    #             pass
    #             #db.session.delete(upload)
    #             #db.session.commit()
    # dicoms = Annotations.query.all()

    # for dicom in dicoms:
    #     thumbnail, _, _, valid_mask = generateThumbnail(f"{dicom_base}{dicom.filename}", f"{upload_base}{dicom.filename}.mask.pkl")
    #     if valid_mask:
    #         shutil.copy(f"{upload_base}{dicom.filename}.mask.pkl", f"{mask_base}{dicom.filename}.mask.pkl")
    #         dicom.annotated = True
    #     dicom.thumbnail = thumbnail
    #     db.session.commit()

    # return render_template('annotation.html')


@app.route('/upload-table', methods=['POST'])
def getUploadsTable():
    uploads_table_header = [
        'filename',
        'tag'
    ]
    if request.method == 'POST':
        uploads = Uploads.query.all()
        table_body = []
        for upload in uploads:
            row = []
            for key in uploads_table_header:
                row.append(getattr(upload, key))
            print(row)
            table_body.append(row[:])

        return jsonify({'body': table_body})


@app.route('/annotation-table', methods=['GET'])
def getAnnotationTable():
    annotation_table_header = [
        'filename',
        'tag',
        'annotated',
        'thumbnail'
    ]
    if request.method == 'GET':
        results = Annotations.query.all()
        table_body = []
        for result in results:
            row = []
            for key in annotation_table_header:
                row.append(getattr(result, key))
            print(row)
            table_body.append(row[:])

        return jsonify({'header': annotation_table_header, 'body': table_body})


@app.route('/results-table', methods=['GET'])
def getResultsTable():
    results_table_header = [
        'thumbnail',
        'filename',
        'tag',
        'result'
    ]
    if request.method == 'GET':
        results = Results.query.all()
        table_body = []
        for result in results:
            row = []
            for key in results_table_header:
                row.append(getattr(result, key))
            print(row)
            table_body.append(row[:])

        return jsonify({'header': results_table_header, 'body': table_body})

@app.route('/inference-status', methods=['GET'])
def inferenceStatus():
    if request.method == 'GET':
        results = Results.query.all()
        print(results)
        table_body = []
        for result in results:
            row = []
            for key in table_header:
                row.append(getattr(result, key))
            table_body.append(row[:])

        return jsonify({'header': table_header, 'body': table_body})

@app.route('/run-model', methods=['POST'])
def runModel():
    if request.method == 'POST':
        dataset = tf.data.TFRecordDataset('train.tfrecords')
        loaded_model = tf.keras.models.load_model(model_base)
        print(loaded_model.predict_on_batch(image_batch)['class'])
        return "Success"
    return 'Error'


@app.route('/get-dicom', methods=['POST'])
def getDicom():
    dicom_name = request.json
    try:
        dcm = pydicom.dcmread(f'{dicom_base}{dicom_name}')
        dicom_data = {
            "transfer_syntax": str(dcm.file_meta.TransferSyntaxUID),
            "slope": 1,
            "intercept": int(min(dcm.pixel_array.flatten())),
            "windowCenter": np.median(dcm.pixel_array),
            "windowWidth": np.std(dcm.pixel_array),
            "rows": dcm.pixel_array.shape[0],
            "columns": dcm.pixel_array.shape[1],
            "minPixelValue": int(min(dcm.pixel_array.flatten())),
            "maxPixelValue": int(max(dcm.pixel_array.flatten())),
            "pixel_data": dcm.pixel_array.flatten().tolist()
        }
    except:
        nifti = nib.load(f'{dicom_base}{dicom_name}')
        dicom_data = {
            "transfer_syntax": '1.2.840.10008.1.2.2',
            "slope": 1,
            "intercept": 0,
            "windowCenter": np.median(nifti.get_data()),
            "windowWidth": np.std(nifti.get_data()),
            "rows": nifti.get_data().shape[0],
            "columns": nifti.get_data().shape[1],
            "minPixelValue": int(min(np.squeeze(nifti.get_data()).flatten())),
            "maxPixelValue": int(max(np.squeeze(nifti.get_data()).flatten())),
            "pixel_data": np.squeeze(nifti.get_data()).flatten().tolist()
        }

    return jsonify(dicom_data)

def windowHelper(value):
    try:
        return list(value)[0]
    except:
        return value


# @app.route('/clear-table', methods=['POST'])
# def clearTable():
#     if request.method == 'POST':
#         delete_folder_contents(data_base)
#         Results.query.delete()
#         db.session.commit()
#         return 'Success'
#     return 'Error'


if __name__ == '__main__':
    print(os.path.curdir)
    # app.run(port=5002, threaded=False)

    # Serve the app with gevent
    http_server = WSGIServer(('0.0.0.0', 5000), app)
    http_server.serve_forever()

