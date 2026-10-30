"""Execute the notebook using THIS interpreter, without global kernel installation."""
from pathlib import Path
import sys
import tempfile
import json
import nbformat
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    notebook_path = ROOT / 'notebooks/ab_analysis.ipynb'
    notebook = nbformat.read(notebook_path, as_version=4)
    with tempfile.TemporaryDirectory(prefix='reactivation-kernel-') as directory:
        kernel_dir = Path(directory) / 'reactivation'
        kernel_dir.mkdir()
        (kernel_dir / 'kernel.json').write_text(json.dumps({
            'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
            'display_name': 'Driver Reactivation', 'language': 'python'}))
        manager = KernelSpecManager(kernel_dirs=[directory])
        client = NotebookClient(notebook, timeout=180, kernel_name='reactivation',
                                resources={'metadata': {'path': str(ROOT / 'notebooks')}})
        client.create_kernel_manager()
        client.km.kernel_spec_manager = manager
        client.execute()
    nbformat.write(notebook, notebook_path)
    print(f'Executed {sum(c.cell_type == "code" for c in notebook.cells)} code cells: {notebook_path.name}')


if __name__ == '__main__':
    main()
