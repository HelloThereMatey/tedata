import os
import subprocess

def generate_docs():
    # Get the directory where this script is located
    root_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(root_dir, 'src')
    
    # Set PYTHONPATH to include src directory
    os.environ['PYTHONPATH'] = f"{src_dir};{os.environ.get('PYTHONPATH', '')}"
    
    # Run pdoc
    subprocess.run([
        'pdoc',
        #'--html',
        '--output-dir', 'docs',
        'src/tedata'
    ], cwd=root_dir)

if __name__ == '__main__':
    generate_docs()