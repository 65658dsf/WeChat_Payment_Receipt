# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import patch

from utools.components.wechat_pay_order import WECHAT_PAY_ORDER
from utools.wechat import pay_order


def _info(text: str, top: int, control_type: str = "Text") -> dict[str, object]:
    return {
        "control_type": control_type,
        "text_blob": text,
        "visible": True,
        "rectangle": {
            "left": 200,
            "top": top,
            "right": 500,
            "bottom": top + 30,
            "width": 300,
            "height": 30,
        },
    }


class PaymentStatusRecognitionTests(unittest.TestCase):
    def _read_status(self, *status_texts: str) -> dict[str, object]:
        root = object()
        controls = [object() for _text in status_texts]
        infos = {
            id(root): {
                "control_type": "Window",
                "text_blob": "微信收款单",
                "visible": True,
                "rectangle": {
                    "left": 100,
                    "top": 100,
                    "right": 600,
                    "bottom": 800,
                    "width": 500,
                    "height": 700,
                },
            }
        }
        infos.update(
            {
                id(control): _info(text, 500 + index * 40)
                for index, (control, text) in enumerate(zip(controls, status_texts))
            }
        )

        with (
            patch.object(
                pay_order,
                "iter_uia_tree",
                return_value=[(root, 0)]
                + [(control, 12) for control in controls],
            ) as iter_tree,
            patch.object(
                pay_order,
                "uia_control_search_info",
                side_effect=lambda control: infos[id(control)],
            ),
        ):
            result = pay_order._read_order_payment_status(root, "ORDER-NOT-VISIBLE")

        iter_tree.assert_called_once_with(
            root,
            max_depth=WECHAT_PAY_ORDER.order_status_uia_max_depth,
        )
        return result

    def test_deep_paid_text_without_visible_order_number_is_paid(self) -> None:
        result = self._read_status("已支付，共计 1 笔")

        self.assertEqual("paid", result["status"])
        self.assertEqual("page_single_explicit_status", result["source"])
        self.assertIsNotNone(result["click_point"])

    def test_unpaid_text_without_visible_order_number_is_unpaid(self) -> None:
        result = self._read_status("暂无人付款")

        self.assertEqual("unpaid", result["status"])
        self.assertEqual("page_single_explicit_status", result["source"])

    def test_conflicting_explicit_statuses_are_unknown(self) -> None:
        result = self._read_status("已支付，共计 1 笔", "暂无人付款")

        self.assertEqual("unknown", result["status"])

    def test_unrelated_page_text_is_unknown(self) -> None:
        result = self._read_status("全部收款单")

        self.assertEqual("unknown", result["status"])


if __name__ == "__main__":
    unittest.main()
