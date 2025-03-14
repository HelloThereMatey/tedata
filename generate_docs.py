import os
import subprocess

## This script generates the documentation for the tedata package using pdoc
## The generated documentation is placed in the docs directory
## The script should be run from the root directory of the project
# Requires pdoc to be installed: pip install pdoc
# pdoc is not included in the requirements.txt file so you'll need to install it manually

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