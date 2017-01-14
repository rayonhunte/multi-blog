import os
import webapp2
import jinja2
import random, string, time, re, hmac
from google.appengine.ext import db

#load template path folder
template_dir = os.path.join(os.path.dirname(__file__),'temp')
#load templateing engine 
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)

# Global regrex 
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASS_RE = re.compile(r"^.{3,20}$")
EMAIL_RE = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")


class User(db.Model):
    """ application user model """
    username = db.StringProperty(required=True)
    password = db.StringProperty(required=True)
    secret = db.StringProperty(required=True)
    email = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)

class BlogPost(db.Model):
    """ application blog model """
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created_by = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)



class Handler(webapp2.RequestHandler):
    """ general template render functions """

    def hash_str(self, in_string, secret):
        """ generate slated hash"""
        return hmac.new(secret, in_string).hexdigest()

    def render_str(self, template, **params):
        """ helper render method"""
        temp = jinja_env.get_template(template)
        return temp.render(params)

    def write(self, *a, **kw):
        """ generic responce"""
        self.response.out.write(*a, **kw)

    def render(self, template, **kw):
        """ generic template render"""
        self.write(self.render_str(template, **kw))



class MainPage(Handler):
    """ Application Landing Page """
    def last_20(self):
        records = db.GqlQuery("select * from BlogPost order by created desc")
        return records.fetch(limit=20)

    def get(self):
        """ render the main application landing page """
        user_d = self.request.cookies.get('user_id')
        if user_d:
            index_dic = {'title':"Rayons Blog", "logout":"Logout", "blogs":self.last_20()}
        else:
            index_dic = {'title':"Rayons Blog"}
        self.render("index.html", **index_dic)

class Signup(Handler):
    """ sing up processing class """

    def val_pass(self, password, verify):
        """ check and verify password """
        if PASS_RE.match(password):
            if password == verify:
                return True, password
            else:
                return False, "Passwords Don't Match"
        else:
            return False, "Invalid Password"

    def val_username(self, username):
        """ username validation"""
        if USER_RE.match(username):
            return True, username
        else:
            return False, "Invalid Username"

    def val_email(self, email):
        """ validate email address """
        if email <> "":
            if EMAIL_RE.match(email):
                return True, email
            return False, "Invalid Email"
        else:
            return True, "No Email"

    def is_user(self, username):
        """ checks if username exist"""
        row = db.GqlQuery("select * from User where username = :1", username)
        if row.fetch(limit=1) == []:
            return True
        else:
            return False

    def get(self):
        """ render Signup page"""
        signup = {'title':"Subscribe to my Blogs", "username":self.request.get("username")}
        self.render("signup.html", **signup)

    def post(self):
        user_val, user = self.val_username(self.request.get("username"))
        pass_val, password = self.val_pass(self.request.get("password"), self.request.get("verify"))
        email = self.request.get("email")
        is_user = self.is_user(user)
        secret = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        if email is not None or email <> "":
            email_val, email = self.val_email(email)
        else:
            email_val = True
        if user_val and pass_val and email_val and is_user:
            hash_pass = self.hash_str(password, secret)
            user = User(username=user, password=hash_pass, secret=secret, email=email)
            user.put()
            user_id = c.key().id()
            self.response.headers.add_header(
                'Set-Cookie', 'user_id=%s|%s; Path=/' % (user_id, hash_pass))
            self.redirect("/welcome")
        else:
            userinv = ""
            passinv = ""
            emailinv = ""
            if user_val == False:
                userinv = "Invalid Username"
            if pass_val == False:
                passinv = "Invalid Password"
            if email_val == False:
                emailinv = "Invalid Email"
            if is_user == False:
                userinv = "User Already exist"
            error_dic = {"useinv":userinv, "passinv":passinv,
                         "emailinv":emailinv, "username":user_val, "email": email}
            self.render("signup.html", **error_dic)

class Welcome(Handler):
    """ main user landing page after login """
    def post_by_user(self, created_by):
        """ get post by user """
        records = db.GqlQuery("select * from BlogPost where created_by = :1 order by created desc", created_by)
        return records.fetch(limit=10)

    def get(self):
        #added pause to allow DB to update for First time User
        time.sleep(1)
        user_d = self.request.cookies.get('user_id')
        if user_d:
            user_id, user_hash = user_d.split("|")
            user = User.get_by_id(int(user_id))
            if user:
                if user.password == user_hash:
                    blog_post = self.post_by_user(user_id)
                    details = {"username":user.username, "logout":"Logout", "blog_post": blog_post}
                    self.render("welcome.html", **details)
                else:
                    self.redirect("/signup")
            else:
                self.redirect("/signup")
        else:
            self.redirect("/signup")
    

class Login(Handler):
    """ application login """
    def get(self):
        """ render login page"""
        self.render("login.html")

    def post(self):
        user = self.request.get("username")
        password = self.request.get("password")
        error = ""
        u = db.GqlQuery("select * from User where username = :1", user)
        user_d = u.fetch(limit=1)
        if user_d <> []:
            secret = str(user_d[0].secret)
            pass_hash = self.hash_str(password, secret)
            if user_d[0].password == pass_hash:
                user_id = user_d[0].key().id()
                self.response.headers.add_header('Set-Cookie', 'user_id=%s|%s; Path=/ ' % (user_id,pass_hash))
                self.redirect("/welcome")
            else:
                error = "Invalid Password"
                self.render("login.html", **{"username":user, "error":error})
        else:
            error = "no such user !!"
            self.render("login.html", **{"username":user, "error":error})
    
class Logout(Handler):
    def get(self):
        self.response.delete_cookie('user_id')
        self.redirect("/signup")

class NewPost(Handler):
    """ new blog post class """

    def get(self):
        """ render new blog post form """
        user_d = self.request.cookies.get('user_id')
        if user_d:
            details = {"logout":"Logout"}
            self.render("new.html", **details)
        else:
            self.redirect("/signup")

    def post(self):
        """ create new blog post """
        subject = self.request.get("subject")
        post = self.request.get("post")
        user_d = self.request.cookies.get('user_id')
        if user_d:
            if subject and post:
                new_post = BlogPost(subject=subject, content=post, created_by=user_d.split("|")[0])
                new_post.put()
                new_post_id = new_post.key().id()
                self.redirect("/single?post_id="+str(new_post_id))
            else:
                details = {"error":"you need both subject and content"}
                self.render("new.html", **details)
        else:
            self.redirect("/login")

class SinglePost(Handler):
     """ display single post"""
    
     def get(self):
        """ render single blog post """
        post_id = self.request.get("post_id")
        blogpost = BlogPost.get_by_id(int(post_id))
        details = {"blogpost":blogpost, "logout":'Logout','post_id':post_id}
        self.render("/single.html", **details)

class Edit(Handler):
    """ Edit Post """

    def get(self):
        """ edit post"""
        post_id = self.request.get("post_id")
        user_d = self.request.cookies.get('user_id')
        if user_d:
            blogpost = BlogPost.get_by_id(int(post_id))
            if blogpost.created_by == user_d.split("|")[0]:
                details = {"blogpost":blogpost, "logout":'Logout', 'post_id':post_id}
                self.render("/edit.html", **details)
            else:
                self.redirect("/signup")
        else:
            self.redirect("/signup")

    def post(self):
        """ supdate blog post """
        user_d = self.request.cookies.get('user_id')
        post_id = self.request.get("post_id")
        subject = self.request.get("subject")
        post = self.request.get("post")
        if user_d:
            blogpost = BlogPost.get_by_id(int(post_id))
            if blogpost.created_by == user_d.split("|")[0]:
                if subject and post:
                    blogpost.subject = subject
                    blogpost.content = post
                    blogpost.put()
                    details = {"blogpost":blogpost, "logout":'Logout', 'post_id':post_id}
                    self.render("/single.html", **details)
                else:
                    details = {"blogpost":blogpost, "logout":'Logout',
                               "error":"you need both subject and content"}
                    self.render("/edit.html", **details)
            else:
                self.redirect("/signup")
    
class Delete(Handler):
    """ delete records """
    def get(self):
        user_d = self.request.cookies.get('user_id')
        post_id = self.request.get("post_id")
        blogpost = BlogPost.get_by_id(int(post_id))
        if user_d:
            if blogpost.created_by == user_d.split("|")[0]:
                blogpost.delete()
                self.redirect("/welcome")
            else:
                self.redirect("/login")
        else:
            self.redirect("/login")

        


app = webapp2.WSGIApplication([
    ('/', MainPage), ('/signup', Signup), ('/welcome', Welcome),
    ('/login', Login), ('/logout', Logout), ('/new', NewPost),
    ('/single', SinglePost), ('/edit', Edit), ('/delete', Delete)] ,debug=True)

