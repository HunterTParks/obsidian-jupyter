import argparse
import sys
from enum import Enum
from jupyter_client import KernelManager
import nbformat
from nbconvert import HTMLExporter
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
import json
import logging

class Kernel(Enum):
    PYTHON = 'python3'
    RUST = 'rust'

# Parse input arguments.
parser = argparse.ArgumentParser()
parser.add_argument('document_id')
args = parser.parse_args()

# Set up a logger that writes to stderr.
logging.basicConfig(level='INFO')
logger = logging.getLogger('obsidian-jupyter')
logger.info('started server for document %s', args.document_id)

# Keep cache of currently selected kernel - defaulted to Python
kernel = Kernel.PYTHON.value

# Create a notebook and kernel.
cell = nbformat.v4.new_code_cell()
nb = nbformat.v4.new_notebook(cells=[cell])
km = KernelManager(kernel_name=kernel)
client = NotebookClient(nb, km)

# Use line buffering.
sys.stdout.reconfigure(line_buffering=True)

try:
    # Respond to each request.
    for request in sys.stdin:
        # Load the request and generate a response with matching id.
        logger.info('received request: %s', request)
        request = json.loads(request)
        request_body = request['body']
        response = {
            'id': request['id'],
        }

        # Execute a cell.
        if request_body['command'] == 'execute':
            # Change Kernel, if necessary
            # This is VERY redundant - figure out how to use MultiKernelManager
            kernel_value = Kernel(request_body['lang']).value
            if kernel != kernel_value:
                kernel = kernel_value
                km = KernelManager(kernel_name=kernel)
                client = NotebookClient(nb, km)

            cell['source'] = request_body['source']
            try:
                nb = client.execute(nb)
            except CellExecutionError as ex:
                logger.info('cell failed to execute: %s', ex)
            html_exporter = HTMLExporter(template_name='basic')
            (response_body, resources) = html_exporter.from_notebook_node(nb)
        elif request_body['command'] == 'restart_kernel':
            km.restart_kernel()
            response_body = ''
        else:
            logger.error('unrecognised command: %s', request_body['command'])
            response_body = ''

        # Pass the response back.
        response['body'] = response_body
        response = json.dumps(response)
        sys.stdout.write(response + '\n')
        sys.stdout.flush()
        logger.info('sent response: %s', response)
finally:
    # Clean up the kernel.
    if km.is_alive:
        logger.info('shutting down kernel...')
        km.shutdown_kernel()

logger.info('exiting...')
