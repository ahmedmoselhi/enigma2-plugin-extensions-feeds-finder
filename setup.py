from distutils.core import setup
import setup_translate


setup(
    name='enigma2-plugin-extensions-feeds-finder',
    version='3.2',
    author='Dimitrij',
    author_email='dima-73@inbox.lv',
    package_dir={
        'Extensions.FeedsFinder': 'src'},
    packages=['Extensions.FeedsFinder'],
    package_data={
        'Extensions.FeedsFinder': [
            '*.png',
            'picon/*.png']},
    description='Find Sattelite Feeds and Scan them',
    cmdclass=setup_translate.cmdclass)
