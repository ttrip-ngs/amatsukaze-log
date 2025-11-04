"""条件式評価ユーティリティ

YAML設定で記述された条件式を安全に評価する
simpleeval ライブラリを使用して、eval()の危険性を回避
"""

from typing import Any

from simpleeval import EvalWithCompoundTypes, NameNotDefined


class ConditionEvaluator:
    """条件式評価器

    simpleeval を使用して安全に条件式を評価

    サポートする演算子:
    - 比較: >, <, >=, <=, ==, !=
    - 論理: and, or, not
    - 括弧: ( )
    - 算術: +, -, *, /, %, **

    サポートする値:
    - ドット記法でのネストアクセス: audiodiff.maxdiff
    - 数値リテラル: 100, 100.0
    - 文字列リテラル: "text", 'text'
    - 真偽値: True, False
    - None

    例:
        >>> evaluator = ConditionEvaluator()
        >>> data = {"audiodiff": {"maxdiff": 150.5}}
        >>> evaluator.evaluate("audiodiff.maxdiff > 100", data)
        True
        >>> evaluator.evaluate("audiodiff.maxdiff > 100 and audiodiff.maxdiff < 200", data)
        True
    """

    def __init__(self) -> None:
        """初期化"""
        # EvalWithCompoundTypes: list, dict, tuple をサポート
        self.evaluator = EvalWithCompoundTypes()

        # 安全のため、関数呼び出しは無効化（デフォルトで無効だが明示）
        self.evaluator.functions = {}

        # 演算子は全てデフォルトで有効
        # 比較演算子: <, >, <=, >=, ==, !=
        # 論理演算子: and, or, not
        # 算術演算子: +, -, *, /, %, **
        # メンバーシップ: in

    def evaluate(self, condition: str, data: dict[str, Any]) -> bool:
        """条件式を評価

        Args:
            condition: 条件式（例: "audiodiff.maxdiff > 100.0"）
            data: 評価対象データ（ネストされた辞書）

        Returns:
            bool: 評価結果

        Raises:
            ValueError: 条件式が不正、または評価エラー

        Examples:
            >>> evaluator = ConditionEvaluator()
            >>> data = {"compression_ratio": 2.5, "src_filesize": 12000000000}
            >>> evaluator.evaluate("compression_ratio < 3.0 and src_filesize > 10000000000", data)
            True
        """
        # データを評価コンテキストに展開
        # ドット記法をサポートするため、ネストされた辞書を平坦化
        names = self._flatten_dict(data)
        self.evaluator.names = names

        try:
            result = self.evaluator.eval(condition)
            return bool(result)
        except NameNotDefined as e:
            # フィールドが存在しない場合はFalse
            return False
        except Exception as e:
            raise ValueError(f"条件式評価エラー: {condition} - {e}") from e

    def _flatten_dict(
        self, data: dict[str, Any], parent_key: str = "", sep: str = "."
    ) -> dict[str, Any]:
        """辞書を平坦化してドット記法をサポート

        Args:
            data: ネストされた辞書
            parent_key: 親キー（再帰用）
            sep: セパレータ

        Returns:
            dict[str, Any]: 平坦化された辞書

        Examples:
            >>> evaluator = ConditionEvaluator()
            >>> data = {"audiodiff": {"maxdiff": 150}}
            >>> evaluator._flatten_dict(data)
            {"audiodiff": {"maxdiff": 150}, "audiodiff.maxdiff": 150}
        """
        items: list[tuple[str, Any]] = []

        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key

            if isinstance(value, dict):
                # ネストされた辞書を再帰的に平坦化
                items.append((new_key, value))  # 元の辞書も保持
                items.extend(self._flatten_dict(value, new_key, sep=sep).items())
            else:
                items.append((new_key, value))

        return dict(items)
