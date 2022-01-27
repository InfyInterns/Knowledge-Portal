import os
import pathlib
import requests
import cachecontrol
from flask import Flask,request,render_template,session,abort,redirect,jsonify
from flask_sqlalchemy import SQLAlchemy
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token

import google.auth.transport.requests

app=Flask(__name__)
app.secret_key="InfyInterns"
app.config['SQLALCHEMY_DATABASE_URI']='postgresql://postgres:password123@localhost/knowledge_portal'
app.config['SQLAlCHEMY_TRACK_MODIFICATIONS']=False
db=SQLAlchemy(app)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID="1005262086641-mmfblvv9m16293ufmop8tufas7qcsqsv.apps.googleusercontent.com"

client_secrets_file=os.path.join(pathlib.Path(__file__).parent,"client_secret.json")
flow=Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"

    )

#Decorator
def login_is_required(function):
    def wrapper(*args,**kwargs):
        if "google_id" not in session:
            return abort(401)
        else:
            return function()
    wrapper.__name__=function.__name__
    return wrapper

class Topic(db.Model):
    __tablename__ = 'topic'
    id = db.Column(db.Integer, primary_key = True)
    topic_title = db.Column(db.String(100), nullable = False)
    topic_description = db.Column(db.String(500), nullable = False)
    posts = db.relationship('Post', backref='topic', lazy='dynamic')


class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key = True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    user_id=db.Column(db.String(100), nullable=False)
    post_title = db. Column(db.String(100), nullable = False)
    post_description = db.Column(db.String(500), nullable = False)

class User(db.Model):
    __tablename__ = 'user'
    google_id = db.Column(db.String(100), primary_key = True)
    name = db. Column(db.String(100), nullable = False)
    email=db.Column(db.String(100),nullable = False)
  

@app.route('/login')
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["email"]=id_info.get("email")
    
    if User.query.get(session["google_id"]) is None:
        user = User(google_id=session["google_id"],name=session["name"],email=session["email"] )
        db.session.add(user)
        db.session.commit()
    
    return redirect('/authorized_area')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/authorized_area')
@login_is_required
def authorized_area():
    return render_template('authorized_page.html')


#Home page
@app.route('/')
def index():
    return render_template('index.html')

#Get all the topics with description
@app.route('/topics', methods = ['GET'])
def gettopics():
    all_topics = []
    topics = Topic.query.all()
    for topic in topics:
        results = {
                    "topic_id":topic.id,
                    "topic_title":topic.topic_title,
                    "topic_description":topic.topic_description, }
        all_topics.append(results)
     
    
    return render_template('topics_page.html', all_topics=all_topics)

#Create Post under a specific topic
@app.route('/post', methods = ['GET','POST'])
@login_is_required
def create_post():
  if request.method == 'POST':
    post_data = request.form
    topic_id= db.session.query(Topic).filter_by(topic_title=post_data['topic_title']).first().id

    user_id=session["google_id"]
    post_title = post_data['post_title']
    post_description = post_data['post_description']

    post = Post(topic_id=topic_id,user_id=user_id,post_title =post_title ,post_description =post_description )

    db.session.add(post)
    db.session.commit()
    
    return render_template('success_page.html')

  else:
      return render_template('createpost_page.html')

#Get all my posts
@app.route('/myposts')
@login_is_required
def get_my_posts():
    all_my_posts = []
    id=session["google_id"]
    myposts=db.session.query(Post).filter_by(user_id=id).all()
    for post in myposts:
          results = {
                    "topic_title":db.session.query(Topic).filter_by(id=post.topic_id).first().topic_title,
                    "topic_id":post.topic_id,
                    "post_id":post.id,
                    "post_title":post.post_title,
                    "post_description":post.post_description, }
          all_my_posts.append(results)

    return render_template('myposts_page.html', all_posts=all_my_posts)


#Get all the posts with description under a specific topic
@app.route('/topics/<int:id>', methods = ['GET'])
def getposts_under_specific_topic(id):
    topic=db.session.query(Topic).filter_by(id=id).first()
    topic_title=topic.topic_title
    all_posts = []
    posts = db.session.query(Post).filter_by(topic_id=id).all()
    for post in posts:
          results = {
                    "post_id":post.id,
                    "post_title":post.post_title,
                    "post_description":post.post_description, }
          all_posts.append(results)
     
    
    return render_template('posts_page.html', all_posts=all_posts,topic_title=topic_title)

#Update the post under a specific topic
@app.route('/update/<int:post_id>', methods = ['GET','PUT'])
def updatepost_under_specific_topic(post_id):

    post_to_be_update=Post.query.get(post_id)
    if request.method == 'PUT':
        post_title = request.json['post_title']
        post_description = request.json['post_description']
        
        post_to_be_update.post_title=post_title
        post_to_be_update.post_description=post_description
        db.session.add(post_to_be_update)
        db.session.commit()
        return jsonify({"success": True, "response": "updated"})
        
     
        

    else:
        return render_template('updatepost_page.html',post_to_be_update=post_to_be_update)


#Delete a post under a specific topic
@app.route('/delete/<post_id>')
def deletepost_under_specific_topic(post_id):
    post_to_be_delete=Post.query.get(post_id)
  
    db.session.delete(post_to_be_delete)
    db.session.commit()
     
    
    return render_template('success_page.html')


if __name__=='__main__':
    app.run(debug=True)
   