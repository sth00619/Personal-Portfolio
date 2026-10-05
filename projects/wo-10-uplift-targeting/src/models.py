"""동일한 학습 표본에서 반응·업리프트 정책 점수를 학습한다."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from causalml.inference.meta import BaseXClassifier
from causalml.inference.tree import UpliftTreeClassifier
from lightgbm import LGBMClassifier, LGBMRegressor
from sklift.models import ClassTransformation, SoloModel, TwoModels

from src.data import DatasetSplit

ESTIMATORS = 80
LEAVES = 15
LEARNING_RATE = 0.05
THREADS = 4
SEED = 42
TREE_TRAIN_ROWS = 100_000
TREE_DEPTH = 4
TREE_MIN_LEAF = 500


def classifier(seed: int = SEED) -> LGBMClassifier:
    """모든 비교군에 같은 복잡도의 이진 분류기를 제공한다."""
    return LGBMClassifier(
        n_estimators=ESTIMATORS,
        num_leaves=LEAVES,
        learning_rate=LEARNING_RATE,
        n_jobs=THREADS,
        random_state=seed,
        verbosity=-1,
    )


def regressor(seed: int = SEED) -> LGBMRegressor:
    """X-learner의 의사 효과를 학습할 회귀기를 제공한다."""
    return LGBMRegressor(
        n_estimators=ESTIMATORS,
        num_leaves=LEAVES,
        learning_rate=LEARNING_RATE,
        n_jobs=THREADS,
        random_state=seed,
        verbosity=-1,
    )


@dataclass
class FittedModels:
    """학습된 모델 및 각 모델의 전처리 메타데이터."""

    response: LGBMClassifier
    t_model: TwoModels
    s_model: SoloModel
    class_transform: ClassTransformation
    class_transform_rows: int
    uplift_tree: UpliftTreeClassifier
    uplift_tree_rows: int
    x_model: BaseXClassifier
    treatment_probability: float

    def scores(self, x: np.ndarray) -> dict[str, np.ndarray]:
        """동일한 평가 행에 대해 각 정책의 순위 점수를 계산한다."""
        tree_potential_outcomes = self.uplift_tree.predict(x.astype(np.float64))
        return {
            "response": self.response.predict_proba(x)[:, 1],
            "t_model": self.t_model.predict(x),
            "s_model": self.s_model.predict(x),
            "class_transformation": self.class_transform.predict(x),
            "uplift_tree": tree_potential_outcomes[:, 1] - tree_potential_outcomes[:, 0],
            "x_model": self.x_model.predict(x, p=np.full(len(x), self.treatment_probability), verbose=False)[:, 0],
        }

    def potential_outcomes(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """T 모델의 잠재결과 확률 예측을 반환한다."""
        self.t_model.predict(x)
        return self.t_model.ctrl_preds_.copy(), self.t_model.trmnt_preds_.copy()


def balanced_class_transformation_indices(treatment: np.ndarray, seed: int = SEED) -> np.ndarray:
    """Class Transformation의 1:1 무작위 배정 가정에 맞는 훈련 인덱스를 만든다."""
    random = np.random.default_rng(seed)
    treated = np.flatnonzero(treatment == 1)
    control = np.flatnonzero(treatment == 0)
    count = min(len(treated), len(control))
    if count == 0:
        raise ValueError("처치군과 대조군이 모두 필요합니다")
    return random.permutation(np.concatenate((random.choice(treated, count, replace=False), random.choice(control, count, replace=False))))


def fit_models(train: DatasetSplit) -> FittedModels:
    """반응 기준선과 T/S/Class Transformation 업리프트 모델을 학습한다."""
    response = classifier()
    response.fit(train.x, train.y)

    t_model = TwoModels(estimator_trmnt=classifier(), estimator_ctrl=classifier(SEED + 1), method="vanilla")
    t_model.fit(train.x, train.y, train.treatment)

    s_model = SoloModel(estimator=classifier(), method="treatment_interaction")
    s_model.fit(train.x, train.y, train.treatment)

    balanced = balanced_class_transformation_indices(train.treatment)
    class_transform = ClassTransformation(estimator=classifier())
    class_transform.fit(train.x[balanced], train.y[balanced], train.treatment[balanced])

    random = np.random.default_rng(SEED)
    tree_indices = random.choice(len(train.y), min(TREE_TRAIN_ROWS, len(train.y)), replace=False)
    tree_treatment = np.where(train.treatment[tree_indices] == 1, "treatment", "control")
    uplift_tree = UpliftTreeClassifier(
        control_name="control",
        max_depth=TREE_DEPTH,
        min_samples_leaf=TREE_MIN_LEAF,
        random_state=SEED,
    )
    uplift_tree.fit(train.x[tree_indices].astype(np.float64), tree_treatment, train.y[tree_indices].astype(np.int64))

    treatment_probability = float(train.treatment.mean())
    x_model = BaseXClassifier(outcome_learner=classifier(), effect_learner=regressor())
    x_model.fit(train.x, train.treatment.astype(np.int64), train.y.astype(np.int64), p=np.full(len(train.y), treatment_probability))

    return FittedModels(response, t_model, s_model, class_transform, len(balanced), uplift_tree, len(tree_indices), x_model, treatment_probability)
