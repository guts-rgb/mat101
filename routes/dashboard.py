"""
Dashboard routes for file upload and viewing results
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import zipfile
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

def get_models():
    """Get models from current app to avoid circular imports"""
    from app import User, Upload, db
    return User, Upload, db

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'm'

def create_user_directories(user_id):
    """Create user-specific directories"""
    user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(user_id))
    user_results_dir = os.path.join(current_app.config['RESULTS_FOLDER'], str(user_id))
    
    os.makedirs(user_upload_dir, exist_ok=True)
    os.makedirs(user_results_dir, exist_ok=True)
    
    return user_upload_dir, user_results_dir

@dashboard_bp.route('/')
@login_required
def dashboard():
    """Main dashboard showing user's uploads and their status"""
    User, Upload, db = get_models()
    
    # Get user's uploads ordered by timestamp (newest first)
    uploads = Upload.query.filter_by(user_id=current_user.id)\
                         .order_by(Upload.timestamp.desc())\
                         .limit(20)\
                         .all()
    
    # Count statistics
    total_uploads = Upload.query.filter_by(user_id=current_user.id).count()
    completed_uploads = Upload.query.filter_by(user_id=current_user.id, status='completed').count()
    failed_uploads = Upload.query.filter_by(user_id=current_user.id, status='failed').count()
    running_uploads = Upload.query.filter_by(user_id=current_user.id, status='running').count()
    
    stats = {
        'total': total_uploads,
        'completed': completed_uploads,
        'failed': failed_uploads,
        'running': running_uploads,
        'pending': total_uploads - completed_uploads - failed_uploads - running_uploads
    }
    
    return render_template('dashboard/dashboard.html', 
                         uploads=uploads, 
                         stats=stats)

@dashboard_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """Handle file upload"""
    if request.method == 'POST':
        # Check if file is in request
        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(request.url)
        
        # Check if file is allowed
        if not allowed_file(file.filename):
            flash('Only .m files are allowed.', 'error')
            return redirect(request.url)
        
        # Secure the filename
        filename = secure_filename(file.filename)
        if not filename:
            flash('Invalid filename.', 'error')
            return redirect(request.url)
        
        # Create user directories
        user_upload_dir, user_results_dir = create_user_directories(current_user.id)
        
        # Add timestamp to filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        # Save file
        file_path = os.path.join(user_upload_dir, unique_filename)
        
        try:
            file.save(file_path)
            
            # Create database record
            upload_record = Upload(
                user_id=current_user.id,
                file_name=filename,
                file_path=file_path,
                status='uploaded'
            )
            db.session.add(upload_record)
            db.session.commit()
            
            flash(f'File "{filename}" uploaded successfully!', 'success')
            return redirect(url_for('dashboard.dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash('Failed to upload file. Please try again.', 'error')
            print(f"Upload error: {e}")
    
    return render_template('dashboard/upload.html')

@dashboard_bp.route('/view/<int:upload_id>')
@login_required
def view_result(upload_id):
    """View execution results for a specific upload"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    # Read log file if exists
    log_content = upload.execution_log or "No execution log available."
    
    # List result files if result_path exists
    result_files = []
    if upload.result_path and os.path.exists(upload.result_path):
        try:
            result_files = os.listdir(upload.result_path)
        except Exception as e:
            print(f"Error reading result directory: {e}")
    
    return render_template('dashboard/result.html', 
                         upload=upload, 
                         log_content=log_content,
                         result_files=result_files)

@dashboard_bp.route('/download/<int:upload_id>')
@login_required
def download_results(upload_id):
    """Download results as ZIP file"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    if not upload.result_path or not os.path.exists(upload.result_path):
        flash('No results available for download.', 'error')
        return redirect(url_for('dashboard.view_result', upload_id=upload_id))
    
    try:
        # Create ZIP file
        zip_filename = f"results_{upload.file_name}_{upload.id}.zip"
        zip_path = os.path.join(upload.result_path, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add execution log
            if upload.execution_log:
                zipf.writestr(f"{upload.file_name}_log.txt", upload.execution_log)
            
            # Add all files in result directory
            for root, dirs, files in os.walk(upload.result_path):
                for file in files:
                    if file != zip_filename:  # Don't include the zip file itself
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, upload.result_path)
                        zipf.write(file_path, arc_name)
        
        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
    
    except Exception as e:
        flash('Failed to create download file.', 'error')
        print(f"Download error: {e}")
        return redirect(url_for('dashboard.view_result', upload_id=upload_id))

@dashboard_bp.route('/delete/<int:upload_id>', methods=['POST'])
@login_required
def delete_upload(upload_id):
    """Delete an upload and its associated files"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    try:
        # Delete files
        if upload.file_path and os.path.exists(upload.file_path):
            os.remove(upload.file_path)
        
        if upload.result_path and os.path.exists(upload.result_path):
            import shutil
            shutil.rmtree(upload.result_path, ignore_errors=True)
        
        # Delete database record
        db.session.delete(upload)
        db.session.commit()
        
        flash('Upload deleted successfully.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete upload.', 'error')
        print(f"Delete error: {e}")
    
    return redirect(url_for('dashboard.dashboard'))