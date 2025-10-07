"""
Execution routes for running MATLAB scripts
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models.upload import Upload
from utils.matlab_runner import MATLABRunner
from app import db
import os
from datetime import datetime

execution_bp = Blueprint('execution', __name__)

@execution_bp.route('/run/<int:upload_id>', methods=['POST'])
@login_required
def run_script(upload_id):
    """Execute MATLAB script"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    # Check if already running or completed
    if upload.status == 'running':
        return jsonify({'error': 'Script is already running'}), 400
    
    # Update status to running
    upload.status = 'running'
    upload.execution_log = 'Starting execution...'
    db.session.commit()
    
    try:
        # Create result directory
        result_dir = os.path.join(
            current_app.config['RESULTS_FOLDER'], 
            str(current_user.id), 
            f"result_{upload.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(result_dir, exist_ok=True)
        
        # Initialize MATLAB runner
        matlab_runner = MATLABRunner()
        
        # Run the script
        success, output, error_msg = matlab_runner.run_script(
            script_path=upload.file_path,
            output_dir=result_dir,
            timeout=300  # 5 minutes timeout
        )
        
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

@execution_bp.route('/status/<int:upload_id>')
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

@execution_bp.route('/cancel/<int:upload_id>', methods=['POST'])
@login_required
def cancel_execution(upload_id):
    """Cancel running script execution"""
    upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first_or_404()
    
    if upload.status != 'running':
        return jsonify({'error': 'Script is not running'}), 400
    
    try:
        # This is a simplified cancellation - in a real implementation,
        # you would need to track the process ID and kill it
        upload.status = 'failed'
        upload.error_message = 'Execution cancelled by user'
        upload.completed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Execution cancelled'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500