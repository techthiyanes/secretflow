# Copyright 2023 Ant Group Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from secretflow.device import PYUObject, PYU
from typing import Dict
from ..pure_numpy_ops.pred import predict_tree_weight


class DistributedTree:
    """A DistributedTree consists of split trees from each party and leaf weight from label holder"""

    def __init__(self):
        self.split_tree_dict = {}
        self.leaf_weight = None
        self.label_holder = None

    def insert_split_tree(self, device: PYU, split_tree: PYUObject):
        """insert a split tree owned by deivce

        Args:
            device (PYU): split tree owner
            split_tree (PYUObject): split tree in disguise
        """
        self.split_tree_dict[device] = split_tree

    def set_leaf_weight(self, label_holder: PYU, leaf_weight: PYUObject):
        """leaf weight is owned by label holder"""
        self.label_holder = label_holder
        self.leaf_weight = leaf_weight

    def predict(self, x: Dict[PYU, PYUObject]) -> PYUObject:
        """predict using a single tree. A single tree is actually consists of all split trees.
        Note the model predict = base + sum of tree predict.
        This is useful in both training and inference

        Args:
            tree (Dict[PYU, PYUObject]): {party: split tree}
            weight (PYUObject): leaf weights from label holder
            x (Dict[PYU, PYUObject]): partitions of FedNdarray. {party: party's partition}

        Returns:
            PYUObject: _description_
        """
        assert len(self.split_tree_dict) == len(
            x
        ), "data parition number should match split tree number"
        assert self.label_holder is not None, "label holder must exist"
        assert len(self.split_tree_dict) > 0, "number of split tree must be not empty"

        weight_selects = list()
        for pyu, split_tree in self.split_tree_dict.items():
            s = pyu(lambda split_tree, x: split_tree.predict_leaf_select(x))(
                split_tree, x[pyu].data
            )
            # worker give selects to label_holder
            weight_selects.append(s.to(self.label_holder))

        weight = self.leaf_weight
        pred = self.label_holder(predict_tree_weight)(weight_selects, weight)
        return pred