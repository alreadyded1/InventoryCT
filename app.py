#!/usr/bin/env python3
"""
Inventory Manager Application
A simple web-based inventory management system
"""
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database setup
DATABASE = 'inventory.db'


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database"""
    conn = get_db()
    cursor = conn.cursor()

    # Create items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            cost REAL,
            quantity INTEGER,
            description TEXT,
            listed_on TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        )
    ''')

    # Migration: Add listed_on column if it doesn't exist
    cursor.execute("PRAGMA table_info(items)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'listed_on' not in columns:
        cursor.execute('ALTER TABLE items ADD COLUMN listed_on TEXT')

    conn.commit()
    conn.close()


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def index():
    """Display all inventory items"""
    conn = get_db()
    cursor = conn.cursor()

    # Get all items with their primary image
    cursor.execute('''
        SELECT i.*, img.filename as primary_image
        FROM items i
        LEFT JOIN images img ON i.id = img.item_id AND img.is_primary = 1
        ORDER BY i.updated_at DESC
    ''')

    items = cursor.fetchall()
    conn.close()

    return render_template('index.html', items=items)


@app.route('/item/<int:item_id>')
def view_item(item_id):
    """View single item details"""
    conn = get_db()
    cursor = conn.cursor()

    # Get item details
    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('index'))

    # Get all images for this item
    cursor.execute('SELECT * FROM images WHERE item_id = ? ORDER BY is_primary DESC', (item_id,))
    images = cursor.fetchall()

    conn.close()

    return render_template('view_item.html', item=item, images=images)


@app.route('/add', methods=['GET', 'POST'])
def add_item():
    """Add new item"""
    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        cost = request.form.get('cost')
        quantity = request.form.get('quantity')
        description = request.form.get('description')
        listed_on = request.form.get('listed_on')

        if not name:
            flash('Item name is required', 'error')
            return redirect(url_for('add_item'))

        conn = get_db()
        cursor = conn.cursor()

        # Insert item
        cursor.execute('''
            INSERT INTO items (name, brand, cost, quantity, description, listed_on)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, brand, float(cost) if cost else None,
              int(quantity) if quantity else 0, description, listed_on))

        item_id = cursor.lastrowid

        # Handle image uploads
        files = request.files.getlist('images')
        for idx, file in enumerate(files):
            if file and file.filename and allowed_file(file.filename):
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Save to database (first image is primary)
                is_primary = 1 if idx == 0 else 0
                cursor.execute('''
                    INSERT INTO images (item_id, filename, is_primary)
                    VALUES (?, ?, ?)
                ''', (item_id, filename, is_primary))

        conn.commit()
        conn.close()

        flash('Item added successfully!', 'success')
        return redirect(url_for('view_item', item_id=item_id))

    return render_template('add_item.html')


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    """Edit existing item"""
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        cost = request.form.get('cost')
        quantity = request.form.get('quantity')
        description = request.form.get('description')
        listed_on = request.form.get('listed_on')

        if not name:
            flash('Item name is required', 'error')
            return redirect(url_for('edit_item', item_id=item_id))

        # Update item
        cursor.execute('''
            UPDATE items
            SET name = ?, brand = ?, cost = ?, quantity = ?, description = ?, listed_on = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name, brand, float(cost) if cost else None,
              int(quantity) if quantity else 0, description, listed_on, item_id))

        # Handle new image uploads
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Check if this is the first image for this item
                cursor.execute('SELECT COUNT(*) as count FROM images WHERE item_id = ?', (item_id,))
                count = cursor.fetchone()['count']
                is_primary = 1 if count == 0 else 0

                cursor.execute('''
                    INSERT INTO images (item_id, filename, is_primary)
                    VALUES (?, ?, ?)
                ''', (item_id, filename, is_primary))

        # Handle image deletions
        delete_images = request.form.getlist('delete_images')
        for image_id in delete_images:
            # Get filename before deleting from DB
            cursor.execute('SELECT filename FROM images WHERE id = ?', (image_id,))
            img = cursor.fetchone()
            if img:
                # Delete file
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
                if os.path.exists(filepath):
                    os.remove(filepath)
                # Delete from database
                cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))

        # Handle primary image selection
        primary_image_id = request.form.get('primary_image')
        if primary_image_id:
            # Unset all primary flags for this item
            cursor.execute('UPDATE images SET is_primary = 0 WHERE item_id = ?', (item_id,))
            # Set new primary
            cursor.execute('UPDATE images SET is_primary = 1 WHERE id = ?', (primary_image_id,))

        conn.commit()
        conn.close()

        flash('Item updated successfully!', 'success')
        return redirect(url_for('view_item', item_id=item_id))

    # GET request - display form
    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('index'))

    cursor.execute('SELECT * FROM images WHERE item_id = ? ORDER BY is_primary DESC', (item_id,))
    images = cursor.fetchall()

    conn.close()

    return render_template('edit_item.html', item=item, images=images)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    """Delete an item"""
    conn = get_db()
    cursor = conn.cursor()

    # Get all images for this item
    cursor.execute('SELECT filename FROM images WHERE item_id = ?', (item_id,))
    images = cursor.fetchall()

    # Delete image files
    for img in images:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)

    # Delete from database (cascade will handle images table)
    cursor.execute('DELETE FROM images WHERE item_id = ?', (item_id,))
    cursor.execute('DELETE FROM items WHERE id = ?', (item_id,))

    conn.commit()
    conn.close()

    flash('Item deleted successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
