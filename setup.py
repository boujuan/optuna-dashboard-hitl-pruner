from setuptools import setup, find_packages

setup(
    name='optuna-dashboard-monitor',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'optuna',
        'optuna-dashboard',
    ],
    entry_points={
        'console_scripts': [
            'optuna-monitor=optuna_monitor.launcher:main',
        ],
    },
    author='Juan Manuel Boullosa Novo',
    author_email='juan.manuel.boullosa.novo@uol.de',
    description='A launcher and human-in-the-loop monitor for Optuna Dashboard.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/boujuan/optuna-dashboard-hitl-pruner',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ],
    python_requires='>=3.7',
)