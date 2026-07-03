from setuptools import find_packages, setup

package_name = 'semantic_fusion'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='abdullah',
    maintainer_email='body20222@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
    'console_scripts': [
        'yolo_node = semantic_fusion.yolo_node:main',
        'fusion_node_master = semantic_fusion.fusion_node:main',
        'semantic_scan_filter = semantic_fusion.semantic_scan_filter:main',
        ],
    },
)
