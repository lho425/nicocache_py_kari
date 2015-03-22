# -*- coding: utf-8 -
# import unittest
#
# import os
# import shutil
# from libnicocache import VideoCacheInfo
#
#
# verbosity = 1
# root_test_dir_path = "./_testdir"
#
#
# class TestVideoCacheInfo(unittest.TestCase):
#
#     def test(self):
#         path = "./cache/subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
#         info = VideoCacheInfo.create_from_cache_file_path(path)
#
#         self.assertEqual(info.video_id, "sm12345")
#         self.assertEqual(info.tmp, True)
#         self.assertEqual(info.low, True)
#         self.assertEqual(info.title, "title56789.avi")
#         self.assertEqual(info.filename_extension, "mp4")
#         self.assertEqual(info.subdir, "subdir1/subdir2")
#
#     def test_no_title(self):
#         path = "./cache/subdir1/subdir2/tmp_sm12345low.mp4"
#         info = VideoCacheInfo.create_from_cache_file_path(path)
#
#         self.assertEqual(info.video_id, "sm12345")
#         self.assertEqual(info.tmp, True)
#         self.assertEqual(info.low, True)
#         self.assertEqual(info.title, "")
#         self.assertEqual(info.filename_extension, "mp4")
#         self.assertEqual(info.subdir, "subdir1/subdir2")
#
#     def test_no_filename_extension(self):
#         path = "./cache/subdir1/subdir2/tmp_sm12345low"
#         info = VideoCacheInfo.create_from_cache_file_path(path)
#
#         self.assertEqual(info.video_id, "sm12345")
#         self.assertEqual(info.tmp, True)
#         self.assertEqual(info.low, True)
#         self.assertEqual(info.title, "")
#         self.assertEqual(info.filename_extension, "")
#         self.assertEqual(info.subdir, "subdir1/subdir2")
#
#     def test_cache_in_top_dir(self):
#         path = "./cache/tmp_sm12345low_title56789.avi.mp4"
#         info = VideoCacheInfo.create_from_cache_file_path(path)
#
#         self.assertEqual(info.video_id, "sm12345")
#         self.assertEqual(info.tmp, True)
#         self.assertEqual(info.low, True)
#         self.assertEqual(info.title, "title56789.avi")
#         self.assertEqual(info.filename_extension, "mp4")
#         self.assertEqual(info.subdir, "")
#
#     def test_make_cache_file_path(self):
#         path = "./cache/subdir1/subdir2/tmp_sm12345low_title56789.avi.mp4"
#         info = VideoCacheInfo.create_from_cache_file_path(path)
#         cachefilepath = VideoCacheInfo.make_cache_file_path(info)
#
#         self.assertEqual(os.path.normpath(cachefilepath),
#                          os.path.normpath(path))
#
#
# class NicoCacheTestCase(unittest.TestCase):
#
#     def make_testdir(self):
#         self.rm_testdir()
#         os.mkdir(os.path.join(root_test_dir_path, self.__class__.__name__))
#
#     def makedir(self, dirname):
#         os.makedirs(
#             os.path.join(root_test_dir_path, self.__class__.__name__, dirname))
#
#     def make_file(self, filename):
#         with open(os.path.join(root_test_dir_path, self.__class__.__name__, filename), "w"):
#             pass
#
#     def rm_testdir(self):
#         shutil.rmtree(
#             os.path.join(root_test_dir_path, self.__class__.__name__), ignore_errors=True)
#
#     def get_real_path(self, path):
#         return os.path.join(root_test_dir_path, self.__class__.__name__,  path)
#
#     def get_testdir_path(self):
#         return os.path.join(root_test_dir_path, self.__class__.__name__)
#
#
# class TestVideoCacheManager(NicoCacheTestCase):
#
#     def setUp(self):
#         self.make_testdir()
#         self.makedir("subdir1")
#         self.makedir("subdir2")
#
#         self.make_file("sm10.mp4")
#         self.make_file("sm11_タイトル.mp4")
#         self.make_file("sm12_タイトル.mp4")
#         self.make_file("subdir1/tmp_so20low_タイトル.mp4")
#
#         self.video_cache_manager = pathutil.FileSystemWrapper()
#
#     def tearDown(self):
#         self.rm_testdir()
#
# def test__get_video_cache_filepath__topdir(self):
# filepath = self.video_cache_manager.\
# get_video_cache_filepath("sm10")
# #
# self.assertEqual(os.path.basename(filepath), "sm10.mp4")
#
#     def test__create_new_file(self):
#         self.video_cache_manager.create_new_file(
#             "sm36", "mp4", tmp=True, low=True, title="普通だな")
#         filepath = self.video_cache_manager.\
#             get_video_cache_filepath("sm36", tmp=True, low=True)
#
#         self.assertEqual(os.path.basename(filepath), "tmp_sm36low_普通だな.mp4")
#
#         self.assertTrue(os.path.exists(filepath))
#
# def test__rename(self):
# oldfilepath = self.video_cache_manager.\
# get_video_cache_filepath("sm10")
# #
# self.video_cache_manager.rename("sm10", tmp=False, low=False,
# new_tmp=True, new_low=True, new_title="新しいタイトル")
# filepath = self.video_cache_manager.\
# get_video_cache_filepath("sm10", tmp=True, low=True)
# #
# self.assertEqual(
# os.path.basename(filepath), "tmp_sm10low_新しいタイトル.mp4")
# #
# self.assertTrue(os.path.exists(filepath))
# #
# self.assertFalse(os.path.exists(oldfilepath))
# #
# def test__create_new_file__already_exist_error(self):
# self.video_cache_manager.create_new_file(
# "sm36", "mp4", tmp=True, low=True, title="普通だな")
# #
# with self.assertRaises(nicocache.NicoCacheFileSystem.AlreadyExistsError):
# self.video_cache_manager.create_new_file(
# "sm36", "mp4", tmp=True, low=True, title="普通だな")
# #
# def test_search_cache_file(self):
# self.make_file("subdir2/tmp_sm98765_うんこ.mp4")
# video_cache_manager = self.video_cache_manager
# self.assertIsNone(video_cache_manager.get_video_cache_filepath(
# "sm98765", tmp=True, low=False))
# self.assertTrue(
# video_cache_manager.search_cache_file(video_id="sm98765",
# filename_extension="mp4",
# tmp=True, low=False,
# title="うんこ"))
# video_cache_manager.get_video_cache_filepath(
# "sm98765", tmp=True, low=False)
# self.assertIsNotNone(
# video_cache_manager.get_video_cache_filepath("sm98765", tmp=True,
# low=False))
#
#
# def test():
#     if os.path.exists(root_test_dir_path):
#         shutil.rmtree(root_test_dir_path)
#     os.mkdir(root_test_dir_path)
#     unittest.main()
# if __name__ == "__main__":
#     test()
