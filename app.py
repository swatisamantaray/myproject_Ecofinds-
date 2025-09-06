import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Product, Order, OrderItem
from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, UPLOAD_FOLDER, allowed_file

CATEGORIES = ['fashion','electronics','home','books','sports','toys','other']

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route('/')
    def index():
        q = request.args.get('q', '').strip().lower()
        category = request.args.get('category', 'all')
        query = Product.query
        if category != 'all':
            query = query.filter_by(category=category)
        if q:
            query = query.filter(Product.title.ilike(f'%{q}%'))
        products = query.order_by(Product.created_at.desc()).all()
        return render_template('index.html', products=products, q=q, category=category, CATEGORIES=CATEGORIES)

    @app.route('/signup', methods=['GET','POST'])
    def signup():
        if request.method == 'POST':
            email = request.form.get('email','').strip().lower()
            username = request.form.get('username','').strip()
            password = request.form.get('password','')
            if not email or not password:
                flash('Email and password are required.','danger'); return redirect(url_for('signup'))
            if User.query.filter_by(email=email).first():
                flash('Email already exists.','warning'); return redirect(url_for('signup'))
            u = User(email=email, username=username); u.set_password(password)
            db.session.add(u); db.session.commit(); login_user(u)
            flash('Account created.','success'); return redirect(url_for('dashboard'))
        return render_template('signup.html')

    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email','').strip().lower()
            password = request.form.get('password','')
            u = User.query.filter_by(email=email).first()
            if not u or not u.check_password(password):
                flash('Invalid credentials.','danger'); return redirect(url_for('login'))
            login_user(u); flash('Welcome back!','success'); return redirect(url_for('index'))
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user(); flash('Logged out.','info'); return redirect(url_for('index'))

    @app.route('/dashboard', methods=['GET','POST'])
    @login_required
    def dashboard():
        if request.method == 'POST':
            username = request.form.get('username','').strip()
            new_email = request.form.get('email','').strip().lower()
            img_url = request.form.get('profile_image','').strip()
            file = request.files.get('file')
            if file and allowed_file(file.filename):
                filename = f'user_{current_user.id}_{file.filename}'
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                img_url = f'/static/uploads/{filename}'
            if new_email and new_email != current_user.email:
                if User.query.filter_by(email=new_email).first():
                    flash('Email already in use.','danger'); return redirect(url_for('dashboard'))
                current_user.email = new_email
            current_user.username = username; current_user.profile_image = img_url
            db.session.commit(); flash('Profile updated.','success'); return redirect(url_for('dashboard'))
        return render_template('dashboard.html')

    @app.route('/add', methods=['GET','POST'])
    @login_required
    def add_product():
        if request.method == 'POST':
            title = request.form.get('title','').strip()
            category = request.form.get('category','other')
            description = request.form.get('description','').strip()
            price = float(request.form.get('price','0') or 0)
            image_url = request.form.get('image','').strip()
            file = request.files.get('file')
            if file and allowed_file(file.filename):
                filename = f'{current_user.id}_{file.filename}'
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f'/static/uploads/{filename}'
            if not title:
                flash('Title is required.','danger'); return redirect(url_for('add_product'))
            p = Product(title=title, category=category, description=description, price=price, image=image_url, owner_id=current_user.id)
            db.session.add(p); db.session.commit(); flash('Product added.','success'); return redirect(url_for('my_listings'))
        return render_template('add_product.html', CATEGORIES=CATEGORIES)

    @app.route('/my-listings')
    @login_required
    def my_listings():
        products = Product.query.filter_by(owner_id=current_user.id).order_by(Product.created_at.desc()).all()
        return render_template('my_listings.html', products=products)

    @app.post('/listing/<int:pid>/update')
    @login_required
    def update_listing(pid):
        p = Product.query.get_or_404(pid)
        if p.owner_id != current_user.id:
            flash('Not authorized.','danger'); return redirect(url_for('my_listings'))
        p.title = request.form.get('title', p.title)
        p.price = float(request.form.get('price', p.price) or p.price)
        p.category = request.form.get('category', p.category)
        p.image = request.form.get('image', p.image)
        db.session.commit(); flash('Listing updated.','success'); return redirect(url_for('my_listings'))

    @app.post('/listing/<int:pid>/delete')
    @login_required
    def delete_listing(pid):
        p = Product.query.get_or_404(pid)
        if p.owner_id != current_user.id:
            flash('Not authorized.','danger'); return redirect(url_for('my_listings'))
        db.session.delete(p); db.session.commit(); flash('Listing deleted.','info'); return redirect(url_for('my_listings'))

    @app.route('/product/<int:pid>')
    def product_detail(pid):
        p = Product.query.get_or_404(pid); return render_template('product_detail.html', p=p)

    def get_cart(): return session.setdefault('cart', [])

    @app.post('/cart/add/<int:pid>')
    def cart_add(pid):
        p = Product.query.get_or_404(pid)
        cart = get_cart(); cart.append({'id':p.id,'title':p.title,'price':p.price,'image':p.image or ''})
        session['cart'] = cart; flash('Added to cart.','success')
        return redirect(url_for('product_detail', pid=pid))

    @app.route('/cart')
    def cart():
        cart = get_cart(); total = sum(float(i.get('price',0)) for i in cart)
        return render_template('cart.html', items=cart, total=total)

    @app.post('/cart/remove/<int:index>')
    def cart_remove(index):
        cart = get_cart()
        if 0 <= index < len(cart):
            cart.pop(index); session['cart'] = cart; flash('Removed item.','info')
        return redirect(url_for('cart'))

    @app.post('/checkout')
    @login_required
    def checkout():
        cart = get_cart()
        if not cart: flash('Cart is empty.','warning'); return redirect(url_for('cart'))
        total = sum(float(i.get('price',0)) for i in cart)
        order = Order(user_id=current_user.id, total=total); db.session.add(order); db.session.flush()
        for it in cart:
            db.session.add(OrderItem(order_id=order.id, product_id=it['id'], title=it['title'], price=it['price'], image=it.get('image','')))
        db.session.commit(); session['cart'] = []; flash('Order placed!','success'); return redirect(url_for('previous_purchases'))

    @app.route('/previous')
    @login_required
    def previous_purchases():
        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template('previous.html', orders=orders)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('not_found.html'), 404

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context(): db.create_all()
    app.run(debug=True)
