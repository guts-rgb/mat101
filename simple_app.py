"""
Flask entry point for MATLAB Script Execution Web App
Simple version with all models defined in main app file
"""
from flask import Flask, render_template, redirect, url_for, flash, request, current_app, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import re
import zipfile
import subprocess
import tempfile
import psutil
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configurations
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.abspath('uploads')
app.config['RESULTS_FOLDER'] = os.path.abspath('results')

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Define models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with uploads
    uploads = db.relationship('Upload', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'

class Upload(db.Model):
    __tablename__ = 'uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    result_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='uploaded')  # uploaded, running, completed, failed
    execution_log = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Upload {self.file_name} - {self.status}>'
    
    @property
    def execution_duration(self):
        """Calculate execution duration if completed"""
        if self.completed_at and self.timestamp:
            return (self.completed_at - self.timestamp).total_seconds()
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility functions
def is_valid_email(email):
    """Simple email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'm'

def create_user_directories(user_id):
    """Create user-specific directories"""
    user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
    user_results_dir = os.path.join(app.config['RESULTS_FOLDER'], str(user_id))
    
    os.makedirs(user_upload_dir, exist_ok=True)
    os.makedirs(user_results_dir, exist_ok=True)
    
    return user_upload_dir, user_results_dir

# MATLAB Runner Class
class MATLABRunner:
    """Handles MATLAB script execution using MATLAB Engine"""
    
    def __init__(self):
        self.matlab_engine = None
        self.matlab_available = False
        self.matlab_error = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize MATLAB Engine"""
        try:
            import matlab.engine
            self.matlab_engine = matlab.engine.start_matlab()
            self.matlab_available = True
            print("✓ MATLAB Engine initialized successfully")
        except ImportError:
            self.matlab_error = "MATLAB Engine for Python is not installed"
            print("✗ MATLAB Engine not available (not installed)")
        except Exception as e:
            self.matlab_error = f"Failed to initialize MATLAB Engine: {str(e)}"
            print(f"✗ Failed to initialize MATLAB Engine: {e}")
    
    def run_script(self, script_path, output_dir, timeout=300):
        """Run a MATLAB script and capture output"""
        if not self.matlab_available or not self.matlab_engine:
            error_msg = f"MATLAB Engine is not available: {self.matlab_error or 'Unknown error'}"
            return False, "", error_msg
        
        return self._run_with_matlab_engine(script_path, output_dir, timeout)
    
    def _run_with_matlab_engine(self, script_path, output_dir, timeout):
        """Run script using MATLAB Engine"""
        try:
            # Ensure output directory exists and is accessible
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # Verify directory is accessible
            if not os.path.isdir(output_dir):
                raise Exception(f"Output directory is not accessible: {output_dir}")
            
            # Read the script content
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Change to output directory and add to MATLAB path
            original_dir = os.getcwd()
            print(f"Changing from {original_dir} to {output_dir}")  # Debug output
            
            try:
                os.chdir(output_dir)
                print(f"Successfully changed to directory: {os.getcwd()}")  # Debug output
                
                # Add output directory to MATLAB path
                self.matlab_engine.addpath(output_dir, nargout=0)
                self.matlab_engine.addpath(os.path.dirname(script_path), nargout=0)
                
                # Create a wrapper script to capture output
                script_name = os.path.basename(script_path)
                script_name_no_ext = os.path.splitext(script_name)[0]
                
                # Instead of using eval, let's use a more direct approach
                # First, copy the original script to the output directory
                output_script_path = os.path.join(output_dir, script_name)
                if not os.path.exists(output_script_path):
                    import shutil
                    shutil.copy2(script_path, output_script_path)
                
                # Create a comprehensive execution log
                execution_output = []
                execution_output.append(f"=== MATLAB Script Execution Report ===")
                execution_output.append(f"Script: {script_name}")
                execution_output.append(f"Execution started: {datetime.now()}")
                execution_output.append(f"Working directory: {output_dir}")
                execution_output.append("")
                
                try:
                    # Change MATLAB's working directory to the output directory
                    matlab_output_dir = output_dir.replace('\\', '/')  # MATLAB prefers forward slashes
                    self.matlab_engine.eval(f"cd('{matlab_output_dir}');", nargout=0)
                    
                    # Verify MATLAB's working directory
                    matlab_pwd = self.matlab_engine.eval("pwd", nargout=1)
                    execution_output.append(f"MATLAB working directory set to: {matlab_pwd}")
                    
                    # Configure MATLAB for headless operation
                    self.matlab_engine.eval("set(0, 'DefaultFigureVisible', 'off');", nargout=0)
                    self.matlab_engine.eval("set(0, 'DefaultFigureCreateFcn', @(fig,~) set(fig, 'Visible', 'off'));", nargout=0)
                    
                    # Start capturing MATLAB output using diary
                    self.matlab_engine.eval("diary('matlab_console.log');", nargout=0)
                    self.matlab_engine.eval("diary on;", nargout=0)
                    
                    execution_output.append("MATLAB configured for headless operation")
                    execution_output.append("MATLAB diary started - capturing console output")
                    execution_output.append("")
                    
                    # Add script directory to MATLAB path
                    script_dir = os.path.dirname(script_path).replace('\\', '/')
                    self.matlab_engine.eval(f"addpath('{script_dir}');", nargout=0)
                    execution_output.append(f"Added script directory to MATLAB path: {script_dir}")
                    
                    # Copy the script to the output directory so MATLAB can access it easily
                    import shutil
                    local_script_path = os.path.join(output_dir, script_name)
                    shutil.copy2(script_path, local_script_path)
                    execution_output.append(f"Copied script to output directory: {local_script_path}")
                    
                    # Execute the script using MATLAB's run function with error handling
                    try:
                        execution_output.append(f"Attempting to run script: {script_name_no_ext}")
                        execution_output.append(f"Original script path: {script_path}")
                        execution_output.append(f"Local script path: {local_script_path}")
                        execution_output.append(f"Current MATLAB working directory: {self.matlab_engine.pwd()}")
                        
                        # Check if script exists
                        script_exists = self.matlab_engine.exist(script_name_no_ext, 'file')
                        execution_output.append(f"Script exists check: {script_exists}")
                        
                        if script_exists != 0:
                            self.matlab_engine.eval(f"run('{script_name_no_ext}');", nargout=0)
                            execution_output.append("Script execution command completed")
                        else:
                            # Try direct evaluation of script content
                            execution_output.append("Script not found via run(), trying direct evaluation...")
                            with open(script_path, 'r', encoding='utf-8') as f:
                                script_content = f.read()
                            self.matlab_engine.eval(script_content, nargout=0)
                            execution_output.append("Direct script evaluation completed")
                    except Exception as script_error:
                        execution_output.append(f"Script execution error: {str(script_error)}")
                        raise script_error
                    
                    # Force save any remaining figures
                    self.matlab_engine.eval("""
                        fig_handles = findall(0, 'Type', 'figure');
                        if ~isempty(fig_handles)
                            fprintf('Found %d figures, ensuring they are saved...\\n', length(fig_handles));
                            for i = 1:length(fig_handles)
                                fig_name = sprintf('additional_figure_%d.png', i);
                                try
                                    print(fig_handles(i), fig_name, '-dpng', '-r300');
                                    fprintf('Saved additional figure: %s\\n', fig_name);
                                catch
                                    fprintf('Failed to save figure %d\\n', i);
                                end
                            end
                            close all;
                        end
                    """, nargout=0)
                    
                    # Stop diary
                    self.matlab_engine.eval("diary off;", nargout=0)
                    
                    # Read MATLAB console output if available
                    matlab_log_path = os.path.join(output_dir, 'matlab_console.log')
                    if os.path.exists(matlab_log_path):
                        try:
                            with open(matlab_log_path, 'r', encoding='utf-8') as f:
                                matlab_output = f.read().strip()
                            if matlab_output:
                                execution_output.append("=== MATLAB Console Output ===")
                                execution_output.append(matlab_output)
                                execution_output.append("=== End MATLAB Console Output ===")
                                execution_output.append("")
                            else:
                                execution_output.append("MATLAB console log exists but is empty")
                        except Exception as e:
                            execution_output.append(f"Could not read MATLAB console log: {str(e)}")
                    else:
                        execution_output.append("No MATLAB console log found")
                    
                    execution_output.append(f"Script execution completed at {datetime.now()}")
                    execution_output.append("")
                    
                    # Force MATLAB to flush any pending file operations
                    self.matlab_engine.eval("pause(0.1);", nargout=0)
                    
                    # List and categorize all created files
                    all_files = [f for f in os.listdir(output_dir) 
                               if os.path.isfile(os.path.join(output_dir, f))]
                    
                    print(f"DEBUG MATLAB: Files found in {output_dir}: {all_files}")
                    
                    script_files = [f for f in all_files if f.endswith('.m')]
                    image_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.svg'))]
                    data_files = [f for f in all_files if f.lower().endswith(('.mat', '.csv', '.txt', '.log'))]
                    other_files = [f for f in all_files if f not in script_files + image_files + data_files]
                    
                    print(f"DEBUG MATLAB: Image files: {image_files}")
                    print(f"DEBUG MATLAB: Data files: {data_files}")
                    print(f"DEBUG MATLAB: Script files: {script_files}")
                    print(f"DEBUG MATLAB: Other files: {other_files}")
                    
                    execution_output.append("=== FILES GENERATED ===")
                    execution_output.append(f"Total files: {len(all_files)}")
                    execution_output.append("")
                    
                    if image_files:
                        execution_output.append(f"📊 Image Files ({len(image_files)}):")
                        for file in sorted(image_files):
                            file_path = os.path.join(output_dir, file)
                            file_size = os.path.getsize(file_path)
                            execution_output.append(f"  - {file} ({file_size:,} bytes)")
                        execution_output.append("")
                    
                    if data_files:
                        execution_output.append(f"📋 Data Files ({len(data_files)}):")
                        for file in sorted(data_files):
                            file_path = os.path.join(output_dir, file)
                            file_size = os.path.getsize(file_path)
                            execution_output.append(f"  - {file} ({file_size:,} bytes)")
                        execution_output.append("")
                    
                    if script_files:
                        execution_output.append(f"📄 Script Files ({len(script_files)}):")
                        for file in sorted(script_files):
                            file_path = os.path.join(output_dir, file)
                            file_size = os.path.getsize(file_path)
                            execution_output.append(f"  - {file} ({file_size:,} bytes)")
                        execution_output.append("")
                    
                    if other_files:
                        execution_output.append(f"📁 Other Files ({len(other_files)}):")
                        for file in sorted(other_files):
                            file_path = os.path.join(output_dir, file)
                            file_size = os.path.getsize(file_path)
                            execution_output.append(f"  - {file} ({file_size:,} bytes)")
                        execution_output.append("")
                    
                    if not any([image_files, data_files, other_files]):
                        execution_output.append("⚠️  No output files were generated by the script")
                        execution_output.append("   This might indicate:")
                        execution_output.append("   - Script completed but didn't create files")
                        execution_output.append("   - Files were saved to a different location")
                        execution_output.append("   - Script had errors preventing file creation")
                    
                    # Create a comprehensive summary file
                    summary_path = os.path.join(output_dir, 'execution_summary.txt')
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        f.write("\\n".join(execution_output))
                    
                    execution_output.append("")
                    execution_output.append(f"📄 Execution summary saved: execution_summary.txt")
                    execution_output.append("")
                    execution_output.append("=== EXECUTION COMPLETED SUCCESSFULLY ===")
                    
                    output = "\\n".join(execution_output)
                    return True, output, None
                    
                except Exception as matlab_error:
                    execution_output.append(f"MATLAB script error: {str(matlab_error)}")
                    output = "\\n".join(execution_output)
                    return False, output, str(matlab_error)
                
            except OSError as e:
                error_msg = f"Cannot change to output directory {output_dir}: {str(e)}"
                return False, error_msg, error_msg
            except Exception as e:
                error_msg = f"MATLAB execution error: {str(e)}"
                return False, error_msg, error_msg
            
            finally:
                os.chdir(original_dir)
        
        except Exception as e:
            return False, "", f"Failed to run script with MATLAB Engine: {str(e)}"

# Initialize MATLAB runner
matlab_runner = MATLABRunner()

# Routes
@app.route('/')
def index():
    """Home page - redirect to dashboard if logged in, otherwise to login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('auth/login.html')
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'error')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return render_template('auth/register.html')
        
        if not is_valid_email(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists.', 'error')
            else:
                flash('Email already registered.', 'error')
            return render_template('auth/register.html')
        
        # Create new user
        try:
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            print(f"Registration error: {e}")
    
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    """Logout and redirect to login page"""
    if current_user.is_authenticated:
        username = current_user.username
        logout_user()
        flash(f'Goodbye, {username}!', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing user's uploads and their status"""
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

@app.route('/upload', methods=['GET', 'POST'])
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
            return redirect(url_for('dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash('Failed to upload file. Please try again.', 'error')
            print(f"Upload error: {e}")
    
    return render_template('dashboard/upload.html')

@app.route('/view/<int:upload_id>')
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

@app.route('/download/<int:upload_id>')
@login_required
def download_results(upload_id):
    """Download results as comprehensive ZIP file"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    if not upload.result_path or not os.path.exists(upload.result_path):
        flash('No results available for download.', 'error')
        return redirect(url_for('view_result', upload_id=upload_id))
    
    try:
        # Create ZIP file
        zip_filename = f"results_{upload.file_name}_{upload.id}.zip"
        zip_path = os.path.join(upload.result_path, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Get all files in result directory
            all_files = []
            print(f"DEBUG: Scanning result directory: {upload.result_path}")
            
            # List all files in the directory for debugging
            try:
                dir_contents = os.listdir(upload.result_path)
                print(f"DEBUG: Directory contents: {dir_contents}")
            except Exception as e:
                print(f"DEBUG: Error listing directory: {e}")
            
            for root, dirs, files in os.walk(upload.result_path):
                print(f"DEBUG: Walking root: {root}, dirs: {dirs}, files: {files}")
                for file in files:
                    if file != zip_filename:  # Don't include the zip file itself
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, upload.result_path)
                        file_size = os.path.getsize(file_path)
                        print(f"DEBUG: Found file: {file} (size: {file_size} bytes)")
                        all_files.append((file_path, rel_path, file))
            
            # Categorize files
            image_files = []
            data_files = []
            script_files = []
            log_files = []
            other_files = []
            
            for file_path, rel_path, filename in all_files:
                lower_name = filename.lower()
                if lower_name.endswith(('.png', '.jpg', '.jpeg', '.pdf', '.svg', '.eps')):
                    image_files.append((file_path, rel_path, filename))
                elif lower_name.endswith(('.mat', '.csv', '.xlsx', '.xls')):
                    data_files.append((file_path, rel_path, filename))
                elif lower_name.endswith('.m'):
                    script_files.append((file_path, rel_path, filename))
                elif lower_name.endswith(('.txt', '.log')):
                    log_files.append((file_path, rel_path, filename))
                else:
                    other_files.append((file_path, rel_path, filename))
            
            # Add files to ZIP with organized folder structure
            
            # 1. Add execution logs and summary
            if upload.execution_log:
                zipf.writestr("📋 Execution Logs/execution_log.txt", upload.execution_log)
            
            # 2. Add log files
            for file_path, rel_path, filename in log_files:
                zipf.write(file_path, f"📋 Execution Logs/{filename}")
            
            # 3. Add image files (plots, figures)
            for file_path, rel_path, filename in image_files:
                zipf.write(file_path, f"📊 Images and Plots/{filename}")
            
            # 4. Add data files (MAT, CSV, etc.)
            for file_path, rel_path, filename in data_files:
                zipf.write(file_path, f"💾 Data Files/{filename}")
            
            # 5. Add script files
            for file_path, rel_path, filename in script_files:
                zipf.write(file_path, f"📄 Scripts/{filename}")
            
            # 6. Add other files
            for file_path, rel_path, filename in other_files:
                zipf.write(file_path, f"📁 Other Files/{filename}")
            
            # 7. Create a comprehensive README
            readme_content = f"""MATLAB Script Execution Results
=================================

Script Name: {upload.file_name}
Upload Date: {upload.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Execution Status: {upload.status.upper()}
Completion Date: {upload.completed_at.strftime('%Y-%m-%d %H:%M:%S') if upload.completed_at else 'N/A'}
Duration: {f"{upload.execution_duration:.2f} seconds" if upload.execution_duration else "N/A"}

📁 FOLDER STRUCTURE:
==================
📋 Execution Logs/    - Console output, execution logs, error messages
📊 Images and Plots/  - PNG, JPG, PDF files (visualizations, charts, graphs)
💾 Data Files/        - MAT, CSV, XLSX files (numerical results, datasets)
📄 Scripts/           - MATLAB .m files (original and generated scripts)  
📁 Other Files/       - Any additional files created by your script

📊 FILE SUMMARY:
===============
• Image Files: {len(image_files)} files
• Data Files: {len(data_files)} files
• Script Files: {len(script_files)} files
• Log Files: {len(log_files)} files
• Other Files: {len(other_files)} files
• Total Files: {len(all_files)} files

🔍 HOW TO USE:
=============
1. 📋 Check "Execution Logs" first to see if your script ran successfully
2. 📊 View "Images and Plots" for any visualizations your script created
3. 💾 Open "Data Files" for numerical results, saved variables, etc.
4. 📄 "Scripts" contains your original code and any generated scripts

💡 FILE FORMATS:
===============
• .png, .jpg, .pdf - Images and plots (can be opened with any image viewer)
• .mat - MATLAB data files (open in MATLAB with 'load filename.mat')
• .csv - Comma-separated values (open in Excel, MATLAB, or any text editor)
• .txt, .log - Text files (open with any text editor)

Generated by MATLAB Script Execution Web App
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            zipf.writestr("README.txt", readme_content)
        
        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
    
    except Exception as e:
        flash('Failed to create download file.', 'error')
        print(f"Download error: {e}")
        return redirect(url_for('view_result', upload_id=upload_id))

@app.route('/run/<int:upload_id>', methods=['POST'])
@login_required
def run_script(upload_id):
    """Execute MATLAB script"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    # Check if already running or completed
    if upload.status == 'running':
        return jsonify({'error': 'Script is already running'}), 400
    
    # Check if MATLAB runner is available
    if not matlab_runner.matlab_available:
        return jsonify({
            'success': False,
            'status': 'failed',
            'error': f'MATLAB Engine is not available: {matlab_runner.matlab_error}'
        }), 500
    
    # Update status to running
    upload.status = 'running'
    upload.execution_log = 'Starting execution...'
    db.session.commit()
    
    try:
        # Create result directory with absolute path
        result_dir = os.path.abspath(os.path.join(
            app.config['RESULTS_FOLDER'], 
            str(current_user.id), 
            f"result_{upload.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ))
        
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(result_dir), exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)
        
        print(f"Created result directory: {result_dir}")  # Debug output
        
        # Run the script
        success, output, error_msg = matlab_runner.run_script(
            script_path=upload.file_path,
            output_dir=result_dir,
            timeout=300  # 5 minutes timeout
        )
        
        # Debug: List files actually created
        try:
            actual_files = os.listdir(result_dir) if os.path.exists(result_dir) else []
            print(f"Files in result directory after execution: {actual_files}")
        except Exception as e:
            print(f"Error listing result directory: {e}")
        
        # Update database with results
        upload.completed_at = datetime.utcnow()
        upload.result_path = result_dir
        upload.execution_log = output
        
        if success:
            upload.status = 'completed'
        else:
            upload.status = 'failed'
            upload.error_message = error_msg
        
        db.session.commit()
        
        return jsonify({
            'success': success,
            'status': upload.status,
            'output': output,
            'error': error_msg
        })
    
    except Exception as e:
        # Update status to failed
        upload.status = 'failed'
        upload.error_message = str(e)
        upload.completed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': False,
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/status/<int:upload_id>')
@login_required
def get_status(upload_id):
    """Get current status of script execution"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    return jsonify({
        'status': upload.status,
        'execution_log': upload.execution_log or '',
        'error_message': upload.error_message or '',
        'completed_at': upload.completed_at.isoformat() if upload.completed_at else None,
        'duration': upload.execution_duration
    })

@app.route('/delete/<int:upload_id>', methods=['POST'])
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
    
    return redirect(url_for('dashboard'))

@app.route('/system-info')
@login_required
def system_info():
    """Display system information and installation status"""
    info = {
        'matlab_available': matlab_runner.matlab_available,
        'matlab_error': matlab_runner.matlab_error,
        'python_version': f"{__import__('sys').version}",
        'platform': f"{os.name} - {__import__('sys').platform}"
    }
    
    if matlab_runner.matlab_available:
        info['matlab_message'] = "MATLAB Engine for Python is properly installed and available"
    
    return render_template('system_info.html', info=info)

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create a default admin user if no users exist
        if User.query.count() == 0:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Created default admin user: admin/admin123")
    
    app.run(debug=True, host='0.0.0.0', port=5000)