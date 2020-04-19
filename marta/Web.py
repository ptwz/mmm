from flask import Flask, render_template, flash, request
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_wtf.file import FileField, FileRequired
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField, SelectField
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from Library import Library

import random
import json

# App config.
DEBUG = True
app = Flask(__name__, template_folder='../web/templates')
Bootstrap(app)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = "".join(random.choices("0123456789abcdef", k=30))
csrf = CSRFProtect(app)

audio_dir = "../audio"
lib = Library(audio_dir)

class UploadForm(FlaskForm):
    # Add option for new card/new directory w/o card yet
    folder = SelectField('Location')
#            default=obj.currentStatus.value)

    filename = FileField()#validators=[FileRequired()])

    def __init__(self, *args, **kwargs):
        form = super(UploadForm, self).__init__(*args, **kwargs)
        dirs = [ ]
        #for subdirs in TagToDir.TAG_TO_DIR.values():
        #    dirs += subdirs
        print (dirs)
        choices=[(i, dirs[i]) for i in range(len(dirs))]
        self.folder.choices = choices
        return form

@app.route('/')
def home():
    mapping = TagToDir.TAG_TO_DIR

    return render_template('index.html', mapping=TagToDir.TAG_TO_DIR)

@app.route('/music/playlist/load', methods=['POST'])
def playlist_load():
    tag = request.args.get("tag", default=None)
    return ""

@app.route('/music/playlist/all', methods=['GET'])
def music_playlist():
    return json.dumps([pl.to_dict() for pl in lib.playlists])
        
@app.route('/music/playlist/assign/<playlist>', methods=['POST'])
def playlist_assign(playlist_id):
    return ""

@app.route('/music/playlist/<tag_or_current>', methods=['GET'])
def playlist(tag_or_current):
    pl = lib.lookup_playlist(tag_or_current)
    if pl:
        return json.dumps(pl.to_dict())

    return ""

@app.route('/music/control', methods=['GET', 'POST'])
def music_control():
    action = request.args.get("tag", default=None)
    if action not in ['start', 'stop', 'song_next', 'song_prev']:
        return ""

@app.route('/music/state', methods=['GET'])
def music_state():
    response = { 
            "tag": None,
            "albums":[],
            "cur_album":None,
            "cur_song":None,
            "cur_position":None
            }
    return json.dumps(response)

@app.route('/volume', methods=['GET', 'POST'])
def volume():
    return ""

@app.route('/power', methods=['GET', 'POST'])
def power():
    return ""

@app.route('/rfid', methods=['GET'])
def rfid():
    return""

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        print(dir(form.filename.data))
        secure_fn= secure_filename(form.filename.data.filename)
        print(secure_fn)
        form.filename.data.save(secure_fn)
    #if form.validate_on_submit():
    #    f = form.photo.data
    #    filename = secure_filename(f.filename)
    #    f.save(os.path.join( app.instance_path, 'photos', filename))
    #    return redirect(url_for('index'))
    print(dir(form))
    return render_template('upload.html', form=form)

#class UploadForm(FlaskForm):
#    name = TextField('Name:', validators=[validators.DataRequired()])
#    
##    def reset(self):
##        blankData = MultiDict([ ('csrf', self.reset_csrf() ) ])
##        self.process(blankData)
#
#    @app.route("/", methods=['GET', 'POST'])
#    def hello():
#        form = ReusableForm(request.form)
#        
#        print(form.errors)
#        if request.method == 'POST':
#            name=request.form['name']
#            print(name)
#        
#        if form.validate():
#        # Save the comment here.
#            flash('Hello ' + name)
#        else:
#            flash('Error: All the form fields are required. ')
#        
#        return render_template('index.html', form=form)

if __name__ == "__main__":
    app.run()
