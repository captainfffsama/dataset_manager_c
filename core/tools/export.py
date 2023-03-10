# -*- coding: utf-8 -*-
"""
@Author: captainfffsama
@Date: 2023-02-28 16:52:46
@LastEditors: captainsama tuanzhangsama@outlook.com
@LastEditTime: 2023-03-02 10:00:03
@FilePath: /dataset_manager/core/tools/exporter.py
@Description:
"""
from typing import Optional

import os
import json
from concurrent import futures

import fiftyone as fo
import fiftyone.core.dataset as focd
from tqdm import tqdm

from core.utils import get_sample_field, md5sum, get_all_file_path
from core.exporter.sgccgame_dataset_exporter import SGCCGameDatasetExporter
from core.logging import logging

from core.cache import WEAK_CACHE


def _export_one_sample_anno(sample, save_dir):
    result = {}
    need_export_map = {
        "data_source": "data_source",
        "img_quality": "img_quality",
        "additions": "additions",
        "tags": "sample_tags",
        "chiebot_ID": "ID",
    }

    for k, v in need_export_map.items():
        vv = get_sample_field(sample, k)
        if vv:
            result[v] = vv

    result["chiebot_sample_tags"] = get_sample_field(
        sample, "chiebot_sample_tags", default=[]
    )

    result["img_shape"] = (
        sample["metadata"].height,
        sample["metadata"].width,
        sample["metadata"].num_channels,
    )
    result["objs_info"] = []
    dets = get_sample_field(sample, "ground_truth")
    if dets:
        for det in dets.detections:
            obj = {}
            obj["name"] = det.label
            obj["pose"] = "Unspecified"
            obj["truncated"] = 0
            obj["difficult"] = 0
            obj["mask"] = []
            obj["confidence"] = -1
            obj["quality"] = 10
            obj["bbox"] = (
                det.bounding_box[0],
                det.bounding_box[1],
                det.bounding_box[0] + det.bounding_box[2],
                det.bounding_box[1] + det.bounding_box[3],
            )

            result["objs_info"].append(obj)

    save_path = os.path.join(save_dir, os.path.splitext(sample.filename)[0] + ".anno")
    with open(save_path, "w") as fw:
        json.dump(result, fw, indent=4, sort_keys=True)

    return save_path


def export_anno_file(
    save_dir: str,
    dataset: Optional[focd.Dataset] = None,
):
    """??????????????????anno????????? save_dir

    Args:
        save_dir (str): ??????anno?????????
        dataset (focd.Dataset,optional): ????????????????????????,?????????????????????????????????
    """
    if dataset is None:
        s = WEAK_CACHE.get("session", None)
        if s is None:
            logging.warning("no dataset in cache,no thing export")
            return
        else:
            dataset = s.dataset
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    with futures.ThreadPoolExecutor(48) as exec:
        tasks = [
            exec.submit(_export_one_sample_anno, sample, save_dir) for sample in dataset
        ]
        for task in tqdm(
            futures.as_completed(tasks),
            total=len(dataset),
            desc="anno????????????:",
            dynamic_ncols=True,
            colour="green",
        ):
            save_path = task.result()

    print("anno ????????????")


def _export_one_sample(sample, exporter, get_anno, save_dir):
    image_path = sample.filepath

    metadata = sample.metadata
    if exporter.requires_image_metadata and metadata is None:
        metadata = fo.ImageMetadata.build_for(image_path)

    # Assumes single label field case
    label = sample["ground_truth"]

    exporter.export_sample(image_path, label, metadata=metadata)

    if get_anno:
        _export_one_sample_anno(sample, save_dir)


def export_sample(
    save_dir: str, dataset: Optional[focd.Dataset] = None, get_anno=True, **kwargs
):
    """???????????????????????????,???????????????anno??????

    Args:
        save_dir (str): ?????????????????????
        dataset (focd.Dataset,optional): ????????????????????????,?????????????????????????????????
        get_anno (bool, optional): ????????????anno. Defaults to True.
        **kwargs: ??????``SGCCGameDatasetExporter`` ?????????
    """
    if dataset is None:
        s = WEAK_CACHE.get("session", None)
        if s is None:
            logging.warning("no dataset in cache,no thing export")
            return
        else:
            dataset = s.dataset
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    if "export_dir" in kwargs:
        kwargs.pop("export_dir")
    exporter = SGCCGameDatasetExporter(export_dir=save_dir, **kwargs)
    with exporter:
        exporter.log_collection(dataset)
        with futures.ThreadPoolExecutor(48) as exec:
            tasks = [
                exec.submit(_export_one_sample, sample, exporter, get_anno, save_dir)
                for sample in dataset
            ]
            for task in tqdm(
                futures.as_completed(tasks),
                total=len(dataset),
                desc="??????????????????:",
                dynamic_ncols=True,
                colour="green",
            ):
                result = task.result()
    print("??????????????????")

