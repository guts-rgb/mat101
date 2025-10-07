"""
MATLAB script runner utility
Handles execution of MATLAB scripts using MATLAB Engine or Octave fallback
"""
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
import signal
import psutil

class MATLABRunner:
    """Handles MATLAB/Octave script execution"""
    
    def __init__(self):
        self.matlab_engine = None
        self.use_octave = False
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize MATLAB Engine or fall back to Octave"""
        try:
            # Try to import and start MATLAB Engine
            import matlab.engine
            self.matlab_engine = matlab.engine.start_matlab()
            print("MATLAB Engine initialized successfully")
        except ImportError:
            print("MATLAB Engine not available, will use Octave fallback")
            self.use_octave = True
        except Exception as e:
            print(f"Failed to initialize MATLAB Engine: {e}")
            print("Will use Octave fallback")
            self.use_octave = True
    
    def run_script(self, script_path, output_dir, timeout=300):
        """
        Run a MATLAB script and capture output
        
        Args:
            script_path (str): Path to the .m file
            output_dir (str): Directory to save outputs
            timeout (int): Timeout in seconds (default 5 minutes)
        
        Returns:
            tuple: (success: bool, output: str, error_message: str)
        """
        if self.use_octave:
            return self._run_with_octave(script_path, output_dir, timeout)
        else:
            return self._run_with_matlab_engine(script_path, output_dir, timeout)
    
    def _run_with_matlab_engine(self, script_path, output_dir, timeout):
        """Run script using MATLAB Engine"""
        try:
            # Read the script content
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Change to output directory
            original_dir = os.getcwd()
            os.chdir(output_dir)
            
            # Add output directory to MATLAB path
            self.matlab_engine.addpath(output_dir, nargout=0)
            
            # Capture output
            output_buffer = []
            
            try:
                # Execute the script
                # Note: This is a simplified version. In practice, you'd want to
                # execute line by line or use evalc for better output capture
                result = self.matlab_engine.eval(script_content, nargout=0)
                
                # List files created in output directory
                created_files = os.listdir(output_dir)
                
                output_buffer.append(f"Script executed successfully at {datetime.now()}")
                output_buffer.append(f"Created files: {created_files}")
                
                return True, '\n'.join(output_buffer), None
                
            except Exception as e:
                error_msg = f"MATLAB execution error: {str(e)}"
                output_buffer.append(error_msg)
                return False, '\n'.join(output_buffer), error_msg
            
            finally:
                # Restore original directory
                os.chdir(original_dir)
        
        except Exception as e:
            return False, "", f"Failed to run script with MATLAB Engine: {str(e)}"
    
    def _run_with_octave(self, script_path, output_dir, timeout):
        """Run script using GNU Octave as fallback"""
        try:
            # Create a wrapper script that changes directory and runs the original script
            script_name = os.path.basename(script_path)
            script_name_no_ext = os.path.splitext(script_name)[0]
            
            wrapper_content = f"""
% Auto-generated wrapper script
cd('{output_dir.replace(os.sep, '/')}');
addpath('{os.path.dirname(script_path).replace(os.sep, '/')}');

fprintf('Starting execution of {script_name} at %s\\n', datestr(now));
fprintf('Output directory: {output_dir}\\n');

try
    % Run the original script
    {script_name_no_ext};
    fprintf('Script completed successfully at %s\\n', datestr(now));
    
    % List created files
    files = dir('.');
    fprintf('Files in output directory:\\n');
    for i = 1:length(files)
        if ~files(i).isdir
            fprintf('  %s\\n', files(i).name);
        end
    end
    
catch exception
    fprintf('Error during execution: %s\\n', exception.message);
    fprintf('Stack trace:\\n');
    for i = 1:length(exception.stack)
        fprintf('  File: %s, Function: %s, Line: %d\\n', ...
                exception.stack(i).file, ...
                exception.stack(i).name, ...
                exception.stack(i).line);
    end
    exit(1);
end
"""
            
            # Write wrapper script
            wrapper_path = os.path.join(output_dir, 'wrapper_script.m')
            with open(wrapper_path, 'w', encoding='utf-8') as f:
                f.write(wrapper_content)
            
            # Run Octave
            cmd = ['octave', '--no-gui', '--quiet', '--eval', f'run("{wrapper_path}")']
            
            # Alternative command for systems where octave might not be in PATH
            alternative_cmds = [
                ['octave-cli', '--quiet', '--eval', f'run("{wrapper_path}")'],
                ['octave.exe', '--no-gui', '--quiet', '--eval', f'run("{wrapper_path}")']
            ]
            
            process = None
            output = ""
            error_msg = None
            
            # Try different octave commands
            for cmd_to_try in [cmd] + alternative_cmds:
                try:
                    process = subprocess.Popen(
                        cmd_to_try,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=output_dir
                    )
                    
                    try:
                        stdout, stderr = process.communicate(timeout=timeout)
                        
                        if process.returncode == 0:
                            output = stdout
                            # Clean up wrapper script
                            try:
                                os.remove(wrapper_path)
                            except:
                                pass
                            return True, output, None
                        else:
                            error_msg = f"Octave execution failed (return code {process.returncode}):\n{stderr}"
                            output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                            break
                    
                    except subprocess.TimeoutExpired:
                        # Kill the process and any child processes
                        try:
                            parent = psutil.Process(process.pid)
                            children = parent.children(recursive=True)
                            for child in children:
                                child.kill()
                            parent.kill()
                        except:
                            pass
                        
                        error_msg = f"Script execution timed out after {timeout} seconds"
                        output = "Execution timed out"
                        break
                
                except FileNotFoundError:
                    continue  # Try next command
                except Exception as e:
                    error_msg = f"Failed to run Octave: {str(e)}"
                    continue
            
            if error_msg is None:
                error_msg = "Octave not found. Please install GNU Octave or MATLAB."
                output = "Neither MATLAB nor Octave could be executed."
            
            # Clean up wrapper script
            try:
                if os.path.exists(wrapper_path):
                    os.remove(wrapper_path)
            except:
                pass
            
            return False, output, error_msg
        
        except Exception as e:
            return False, "", f"Failed to run script with Octave: {str(e)}"
    
    def __del__(self):
        """Clean up MATLAB Engine when object is destroyed"""
        if self.matlab_engine:
            try:
                self.matlab_engine.quit()
            except:
                pass