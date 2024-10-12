from setuptools import setup, find_packages

setup(
   name='llm-shell',
   version='0.5.0',
   packages=find_packages(),
   install_requires=[
       'requests',
       'pygments',
   ],
   entry_points={
       'console_scripts': [
            'llm-shell=llm_shell.llm_shell:main',
            'llm-shell-ask=llm_shell.llm_shell:ask_llm',
       ],
   },
   # Metadata
   author='Mirror12k',
   description='A Language Model Enhanced Command Line Interface',
   long_description=open('README.md').read(),
   long_description_content_type='text/markdown',
   license='MIT',
   keywords='shell with integrated access to chatgpt or other llms',
   url='https://github.com/mirror12k/llm-shell',
   classifiers=[
       'Programming Language :: Python :: 3',
       'License :: OSI Approved :: MIT License',
   ],
)
