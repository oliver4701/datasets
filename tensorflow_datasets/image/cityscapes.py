'''Cityscapes Datasets.'''

import math
import os
import re

import tensorflow as tf
import tensorflow_datasets.public_api as tfds
from tensorflow_datasets.core import api_utils

_CITATION = '''\
@inproceedings{Cordts2016Cityscapes,
  title={The Cityscapes Dataset for Semantic Urban Scene Understanding},
  author={Cordts, Marius and Omran, Mohamed and Ramos, Sebastian and Rehfeld, Timo and Enzweiler, Markus and Benenson, Rodrigo and Franke, Uwe and Roth, Stefan and Schiele, Bernt},
  booktitle={Proc. of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)},
  year={2016}
}
'''

_DESCRIPTION = '''\
  Cityscapes is a dataset consisting of diverse urban street scenes across 50 different cities
  at varying times of the year as well as ground truths for several vision tasks including
  semantic segmentation, instance level segmentation (TODO), and stereo pair disparity inference.


  For segmentation tasks (default split, accessible via 'cityscapes/semantic_segmentation'), Cityscapes provides
  dense pixel level annotations for 5000 images at 1024 * 2048 resolution pre-split into training (2975),
  validation (500) and test (1525) sets. Label annotations for segmentation tasks span across 30+ classes
  commonly encountered during driving scene perception. Detailed label information may be found here:
  https://github.com/mcordts/cityscapesScripts/blob/master/cityscapesscripts/helpers/labels.py#L52-L99

  Cityscapes also provides coarse grain segmentation annotations (accessible via 'cityscapes/semantic_segmentation_extra')
  for 19998 images in a 'train_extra' split which may prove useful for pretraining / data-heavy models.


  Besides segmentation, cityscapes also provides stereo image pairs and ground truths for disparity inference
  tasks on both the normal and extra splits (accessible via 'cityscapes/stereo_disparity' and 
  'cityscapes/stereo_disparity_extra' respectively).

  Ingored examples:
  - For 'cityscapes/stereo_disparity_extra':
    - troisdorf_000000_000073_{*} images (no disparity map present)

  WARNING: this dataset requires users to setup a login and password in order to get the files.
'''

# TODO add instance ids (might need to import cityScapesScripts)

class CityscapesConfig(tfds.core.BuilderConfig):
  '''BuilderConfig for Cityscapes

    Args:
      right_images (bool): Enables right images for stereo image tasks.
      segmentation_labels (bool): Enables image segmentation labels.
      disparity_maps (bool): Enables disparity maps.
      train_extra_split (bool): Enables train_extra split. This automatically
          enables coarse grain segmentations, if segmentation labels are used.
  '''

  @api_utils.disallow_positional_args
  def __init__(self, right_images=False, segmentation_labels=True,
               disparity_maps=False, train_extra_split=False, **kwargs):
    super().__init__(**kwargs)

    self.right_images = right_images
    self.segmentation_labels = segmentation_labels
    self.disparity_maps = disparity_maps
    self.train_extra_split = train_extra_split

    self.ignored_ids = set()

    # Setup required zips and their root dir names
    self.zip_root = {}
    self.zip_root['images_left'] =\
      ('leftImg8bit_trainvaltest.zip', 'leftImg8bit')

    if self.train_extra_split:
      self.zip_root['images_left/extra'] =\
        ('leftImg8bit_trainextra.zip', 'leftImg8bit')

    if self.right_images:
      self.zip_root['images_right'] =\
        ('rightImg8bit_trainvaltest.zip', 'rightImg8bit')
      if self.train_extra_split:
        self.zip_root['images_right/extra'] =\
          ('rightImg8bit_trainextra.zip', 'rightImg8bit')

    if self.segmentation_labels:
      if not self.train_extra_split:
        self.zip_root['segmentation_labels'] =\
          ('gtFine_trainvaltest.zip', 'gtFine')
        self.label_suffix = 'gtFine_labelIds'
      else:
        # The 'train extra' split only has coarse labels unlike train and val.
        # Therefore, for consistency across splits, we also enable coarse labels
        # using the train_extra_split flag.
        self.zip_root['segmentation_labels'] = ('gtCoarse.zip', 'gtCoarse')
        self.zip_root['segmentation_labels/extra'] = \
          ('gtCoarse.zip', 'gtCoarse')
        self.label_suffix = 'gtCoarse_labelIds'

    if self.disparity_maps:
      self.zip_root['disparity_maps'] =\
        ('disparity_trainvaltest.zip', 'disparity')
      if self.train_extra_split:
        self.zip_root['disparity_maps/extra'] =\
          ('disparity_trainextra.zip', 'disparity')
        self.ignored_ids.add('troisdorf_000000_000073') # No disparity for this file


class Cityscapes(tfds.core.GeneratorBasedBuilder):
  '''Base class for Cityscapes datasets'''

  BUILDER_CONFIGS = [
      CityscapesConfig(
          name='semantic_segmentation',
          description='Cityscapes semantic segmentation dataset.',
          version="1.0.0",
          right_images=False,
          segmentation_labels=True,
          disparity_maps=False,
          train_extra_split=False,
      ),
      CityscapesConfig(
          name='semantic_segmentation_extra',
          description='Cityscapes semantic segmentation dataset with train_extra split and coarse labels.', # pylint: disable=line-too-long
          version="1.0.0",
          right_images=False,
          segmentation_labels=True,
          disparity_maps=False,
          train_extra_split=True,
      ),
      CityscapesConfig(
          name='stereo_disparity',
          description='Cityscapes stereo image and disparity maps dataset.',
          version="1.0.0",
          right_images=True,
          segmentation_labels=False,
          disparity_maps=True,
          train_extra_split=False,
      ),
      CityscapesConfig(
          name='stereo_disparity_extra',
          description='Cityscapes stereo image and disparity maps dataset with train_extra split.', # pylint: disable=line-too-long
          version="1.0.0",
          right_images=True,
          segmentation_labels=False,
          disparity_maps=True,
          train_extra_split=True,
      ),
  ]

  VERSION = tfds.core.Version('1.0.0')

  def _info(self):
    # Enable features as necessary
    features = {}
    features['image_id'] = tfds.features.Text()
    features['image_left'] =\
      tfds.features.Image(shape=(1024, 2048, 3), encoding_format='png')

    if self.builder_config.right_images:
      features['image_right'] =\
        tfds.features.Image(shape=(1024, 2048, 3), encoding_format='png')

    if self.builder_config.segmentation_labels:
      features['segmentation_label'] =\
        tfds.features.Image(shape=(1024, 2048, 1), encoding_format='png')

    if self.builder_config.disparity_maps:
      features['disparity_map'] =\
        tfds.features.Image(shape=(1024, 2048, 1), encoding_format='png')

    return tfds.core.DatasetInfo(
        builder=self,
        description=(_DESCRIPTION),
        features=tfds.features.FeaturesDict(features),
        urls=['https://www.cityscapes-dataset.com', 'https://github.com/mcordts/cityscapesScripts'],
        citation=_CITATION,
    )

  def _split_generators(self, dl_manager):
    paths = {}
    for split, (zip_file, zip_root) in self.builder_config.zip_root.items():
      paths[split] = os.path.join(dl_manager.manual_dir, zip_file)

    if any(not os.path.exists(z) for z in paths.values()):
      msg = 'You must download the dataset files manually and place them in: '
      msg += ', '.join(paths.values())
      raise AssertionError(msg)

    for split, (_, zip_root) in self.builder_config.zip_root.items():
      paths[split] = os.path.join(dl_manager.extract(paths[split]), zip_root)

    features_size_mb = 6 # 1024 * 2048 * 3 = 6MB (left image always present)
    if self.builder_config.right_images:
      features_size_mb += 6 # 1024 * 2048 * 3 = 6MB
    if self.builder_config.segmentation_labels:
      features_size_mb += 2 # 1024 * 2048 * 1 = 2MB
    if self.builder_config.disparity_maps:
      features_size_mb += 2 # 1024 * 2048 * 1 = 2MB

    def calculate_num_shards(split_size, features_size_mb):
      ''' Calculates the number of shards '''
      # Each shard must be strictly less than 4gb
      instances_per_shard = math.floor(4096 / features_size_mb)
      return math.ceil(split_size / instances_per_shard)

    splits = [
        tfds.core.SplitGenerator(
            name=tfds.Split.TRAIN,
            num_shards=calculate_num_shards(2975, features_size_mb),
            gen_kwargs={
                feat_dir: os.path.join(path, 'train')
                for feat_dir, path in paths.items()
                if not feat_dir.endswith('/extra')
            },
        ),
        tfds.core.SplitGenerator(
            name=tfds.Split.VALIDATION,
            num_shards=calculate_num_shards(500, features_size_mb),
            gen_kwargs={
                feat_dir: os.path.join(path, 'val')
                for feat_dir, path in paths.items()
                if not feat_dir.endswith('/extra')
            },
        ),
    ]

    # Test split does not exist in coarse dataset
    if not self.builder_config.train_extra_split:
      splits.append(tfds.core.SplitGenerator(
          name=tfds.Split.TEST,
          num_shards=calculate_num_shards(1525, features_size_mb),
          gen_kwargs={
              feat_dir: os.path.join(path, 'test')
              for feat_dir, path in paths.items()
              if not feat_dir.endswith('/extra')
          },
      ))
    else:
      splits.append(tfds.core.SplitGenerator(
          name='train_extra',
          num_shards=calculate_num_shards(19998, features_size_mb),
          gen_kwargs={
              feat_dir.replace('/extra', ''): os.path.join(path, 'train_extra')
              for feat_dir, path in paths.items()
              if feat_dir.endswith('/extra')
          },
      ))
    return splits

  def _generate_examples(self, **paths):
    left_imgs_root = paths['images_left']
    for city_id in tf.io.gfile.listdir(left_imgs_root):
      paths_city_root = {feat_dir: os.path.join(path, city_id)
                         for feat_dir, path in paths.items()}

      left_city_root = paths_city_root['images_left']
      for left_img in tf.io.gfile.listdir(left_city_root):
        left_img_path = os.path.join(left_city_root, left_img)
        image_id = _get_left_image_id(left_img)

        if image_id in self.builder_config.ignored_ids:
          continue

        features = {
            'image_id': image_id,
            'image_left': left_img_path
        }

        if self.builder_config.right_images:
          features['image_right'] = os.path.join(
              paths_city_root['images_right'], f'{image_id}_rightImg8bit.png')

        if self.builder_config.segmentation_labels:
          features['segmentation_label'] = os.path.join(
              paths_city_root['segmentation_labels'],
              f'{image_id}_{self.builder_config.label_suffix}.png')

        if self.builder_config.disparity_maps:
          features['disparity_map'] = os.path.join(
              paths_city_root['disparity_maps'], f'{image_id}_disparity.png')

        yield image_id, features

# Helper functions

LEFT_IMAGE_FILE_RE = re.compile(r'([a-z\-]+)_(\d+)_(\d+)_leftImg8bit\.png')

def _get_left_image_id(left_image):
  '''Returns the id of an image file. Used to associate an image file
  with its corresponding label.
  Example:
    'bonn_000001_000019_leftImg8bit' -> 'bonn_000001_000019'
  '''
  match = LEFT_IMAGE_FILE_RE.match(left_image)
  return f'{match.group(1)}_{match.group(2)}_{match.group(3)}'
