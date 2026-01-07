"""条件式評価ユーティリティのテスト"""

import pytest

from src.utils.condition_evaluator import ConditionEvaluator


class TestConditionEvaluator:
    """ConditionEvaluatorクラスのテスト"""

    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        """評価器インスタンス"""
        return ConditionEvaluator()

    def test_simple_comparison_greater(self, evaluator: ConditionEvaluator) -> None:
        """単純な比較（大なり）"""
        data = {"value": 100}
        assert evaluator.evaluate("value > 50", data) is True
        assert evaluator.evaluate("value > 100", data) is False

    def test_simple_comparison_less(self, evaluator: ConditionEvaluator) -> None:
        """単純な比較（小なり）"""
        data = {"value": 50}
        assert evaluator.evaluate("value < 100", data) is True
        assert evaluator.evaluate("value < 50", data) is False

    def test_simple_comparison_equal(self, evaluator: ConditionEvaluator) -> None:
        """単純な比較（等価）"""
        data = {"value": 100}
        assert evaluator.evaluate("value == 100", data) is True
        assert evaluator.evaluate("value == 50", data) is False

    def test_nested_access_dot_notation(self, evaluator: ConditionEvaluator) -> None:
        """ドット記法でのネストアクセス"""
        data = {"audiodiff": {"maxdiff": 150.5}}
        assert evaluator.evaluate("audiodiff.maxdiff > 100", data) is True
        assert evaluator.evaluate("audiodiff.maxdiff < 200", data) is True
        assert evaluator.evaluate("audiodiff.maxdiff > 200", data) is False

    def test_deeply_nested_access(self, evaluator: ConditionEvaluator) -> None:
        """深いネストへのアクセス"""
        data = {"level1": {"level2": {"level3": 42}}}
        assert evaluator.evaluate("level1.level2.level3 == 42", data) is True

    def test_compound_condition_and(self, evaluator: ConditionEvaluator) -> None:
        """複合条件式（and）"""
        data = {"compression_ratio": 2.5, "src_filesize": 12000000000}
        assert (
            evaluator.evaluate(
                "compression_ratio < 3.0 and src_filesize > 10000000000", data
            )
            is True
        )
        assert (
            evaluator.evaluate(
                "compression_ratio < 2.0 and src_filesize > 10000000000", data
            )
            is False
        )

    def test_compound_condition_or(self, evaluator: ConditionEvaluator) -> None:
        """複合条件式（or）"""
        data = {"error_count": 5, "warn_count": 10}
        assert evaluator.evaluate("error_count > 3 or warn_count > 100", data) is True
        assert evaluator.evaluate("error_count > 10 or warn_count > 100", data) is False

    def test_compound_condition_not(self, evaluator: ConditionEvaluator) -> None:
        """複合条件式（not）"""
        data = {"is_success": False}
        assert evaluator.evaluate("not is_success", data) is True
        data = {"is_success": True}
        assert evaluator.evaluate("not is_success", data) is False

    def test_parentheses(self, evaluator: ConditionEvaluator) -> None:
        """括弧を使用した条件式"""
        data = {"a": 1, "b": 2, "c": 3}
        # (a > 0 and b > 0) or c > 10 → True
        assert evaluator.evaluate("(a > 0 and b > 0) or c > 10", data) is True
        # a > 0 and (b > 10 or c > 10) → False
        assert evaluator.evaluate("a > 0 and (b > 10 or c > 10)", data) is False

    def test_arithmetic_in_condition(self, evaluator: ConditionEvaluator) -> None:
        """算術演算を含む条件式"""
        data = {"src_size": 1000, "out_size": 200}
        assert evaluator.evaluate("src_size / out_size > 4", data) is True
        assert evaluator.evaluate("src_size - out_size == 800", data) is True

    def test_undefined_field_returns_false(
        self, evaluator: ConditionEvaluator
    ) -> None:
        """存在しないフィールドへのアクセスはFalse"""
        data = {"existing": 100}
        assert evaluator.evaluate("nonexistent > 50", data) is False

    def test_invalid_condition_raises_error(
        self, evaluator: ConditionEvaluator
    ) -> None:
        """不正な条件式はValueError"""
        data = {"value": 100}
        with pytest.raises(ValueError, match="条件式評価エラー"):
            evaluator.evaluate("value >< 50", data)

    def test_flatten_dict_simple(self, evaluator: ConditionEvaluator) -> None:
        """辞書平坦化（シンプル）"""
        data = {"a": 1, "b": 2}
        result = evaluator._flatten_dict(data)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_flatten_dict_nested(self, evaluator: ConditionEvaluator) -> None:
        """辞書平坦化（ネスト）"""
        data = {"audiodiff": {"maxdiff": 150, "avgdiff": 50}}
        result = evaluator._flatten_dict(data)
        assert result["audiodiff.maxdiff"] == 150
        assert result["audiodiff.avgdiff"] == 50
        # 元の辞書も保持されている
        assert result["audiodiff"]["maxdiff"] == 150

    def test_flatten_dict_deeply_nested(self, evaluator: ConditionEvaluator) -> None:
        """辞書平坦化（深いネスト）"""
        data = {"level1": {"level2": {"level3": {"value": 42}}}}
        result = evaluator._flatten_dict(data)
        assert result["level1.level2.level3.value"] == 42

    def test_empty_data(self, evaluator: ConditionEvaluator) -> None:
        """空のデータ"""
        data: dict = {}
        # 存在しないフィールドへのアクセスはFalse
        assert evaluator.evaluate("value > 50", data) is False

    def test_boolean_values(self, evaluator: ConditionEvaluator) -> None:
        """真偽値"""
        data = {"flag": True, "other_flag": False}
        assert evaluator.evaluate("flag == True", data) is True
        assert evaluator.evaluate("other_flag == False", data) is True
        assert evaluator.evaluate("flag and not other_flag", data) is True

    def test_string_comparison(self, evaluator: ConditionEvaluator) -> None:
        """文字列比較"""
        data = {"status": "success"}
        assert evaluator.evaluate('status == "success"', data) is True
        assert evaluator.evaluate('status == "failed"', data) is False

    def test_float_precision(self, evaluator: ConditionEvaluator) -> None:
        """浮動小数点精度"""
        data = {"ratio": 0.3333333333}
        assert evaluator.evaluate("ratio > 0.33", data) is True
        assert evaluator.evaluate("ratio < 0.34", data) is True
