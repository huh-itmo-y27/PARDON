"""
Local copy of SKAB changepoint metrics.
Originally sourced from SKAB/core/metrics.py.
"""

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def filter_detecting_boundaries(detecting_boundaries):
    _detecting_boundaries = []
    for couple in detecting_boundaries.copy():
        if len(couple) != 0:
            _detecting_boundaries.append(couple)
    detecting_boundaries = _detecting_boundaries
    return detecting_boundaries


def single_detecting_boundaries(
    true_series,
    true_list_ts,
    prediction,
    portion,
    window_width,
    anomaly_window_destination,
    intersection_mode,
):
    if (true_series is not None) and (true_list_ts is not None):
        raise Exception("Choose the ONE type")
    elif true_series is not None:
        true_timestamps = true_series[true_series == 1].index
    elif true_list_ts is not None:
        if len(true_list_ts) == 0:
            return [[]]
        true_timestamps = true_list_ts
    else:
        raise Exception("Choose the type")

    detecting_boundaries = []
    td = (
        pd.Timedelta(window_width)
        if window_width is not None
        else pd.Timedelta(
            (prediction.index[-1] - prediction.index[0])
            / (len(true_timestamps) + 1)
            * portion
        )
    )
    for val in true_timestamps:
        if anomaly_window_destination == "lefter":
            detecting_boundaries.append([val - td, val])
        elif anomaly_window_destination == "righter":
            detecting_boundaries.append([val, val + td])
        elif anomaly_window_destination == "center":
            detecting_boundaries.append([val - td / 2, val + td / 2])
        else:
            raise RuntimeError("choose anomaly_window_destination")

    if len(detecting_boundaries) == 0:
        return detecting_boundaries

    new_detecting_boundaries = detecting_boundaries.copy()
    for i in range(len(new_detecting_boundaries) - 1):
        if (
            new_detecting_boundaries[i][1]
            >= new_detecting_boundaries[i + 1][0]
        ):
            if intersection_mode == "cut left window":
                new_detecting_boundaries[i][1] = new_detecting_boundaries[
                    i + 1
                ][0]
            elif intersection_mode == "cut right window":
                new_detecting_boundaries[i + 1][0] = new_detecting_boundaries[
                    i
                ][1]
            elif intersection_mode == "cut both":
                _a = new_detecting_boundaries[i][1]
                new_detecting_boundaries[i][1] = new_detecting_boundaries[
                    i + 1
                ][0]
                new_detecting_boundaries[i + 1][0] = _a
            else:
                raise Exception("choose the intersection_mode")
    detecting_boundaries = new_detecting_boundaries.copy()
    return detecting_boundaries


def check_errors(my_list):
    assert isinstance(my_list, list)
    mx = 1
    level_list = {}

    def check_error(items):
        return not (
            (all(isinstance(my_el, list) for my_el in items))
            or (all(isinstance(my_el, pd.Series) for my_el in items))
            or (all(isinstance(my_el, pd.Timestamp) for my_el in items))
        )

    def recurse(items, level=1):
        nonlocal mx
        nonlocal level_list

        if check_error(items):
            raise Exception(f"Non uniform data format in level {level}: {items}")

        if level not in level_list.keys():
            level_list[level] = []

        for my_el in items:
            level_list[level].append(my_el)
            if isinstance(my_el, list):
                mx = max([mx, level + 1])
                recurse(my_el, level + 1)

    recurse(my_list)
    for level in level_list:
        if check_error(level_list[level]):
            raise Exception(
                f"Non uniform data format in level {level}: {my_list}"
            )

    if 3 in level_list:
        for el in level_list[2]:
            if not ((len(el) == 2) or (len(el) == 0)):
                raise Exception(f"Non uniform data format in level {2}: {my_list}")
    return mx


def extract_cp_confusion_matrix(
    detecting_boundaries, prediction, point=0, binary=False
):
    _detecting_boundaries = []
    for couple in detecting_boundaries.copy():
        if len(couple) != 0:
            _detecting_boundaries.append(couple)
    detecting_boundaries = _detecting_boundaries

    times_pred = prediction[prediction.dropna() == 1].sort_index().index

    my_dict = {"TPs": {}, "FPs": [], "FNs": []}

    if len(detecting_boundaries) != 0:
        my_dict["FPs"].append(times_pred[times_pred < detecting_boundaries[0][0]])
        for i in range(len(detecting_boundaries)):
            times_pred_window = times_pred[
                (times_pred >= detecting_boundaries[i][0])
                & (times_pred <= detecting_boundaries[i][1])
            ]
            times_prediction_in_window = prediction[
                detecting_boundaries[i][0] : detecting_boundaries[i][1]
            ].index
            if len(times_pred_window) == 0:
                if not binary:
                    my_dict["FNs"].append(i)
                else:
                    my_dict["FNs"].append(times_prediction_in_window)
            else:
                my_dict["TPs"][i] = [
                    detecting_boundaries[i][0],
                    times_pred_window[point] if not binary else times_pred_window,
                    detecting_boundaries[i][1],
                ]
                if binary:
                    my_dict["FNs"].append(
                        times_prediction_in_window[
                            ~times_prediction_in_window.isin(times_pred_window)
                        ]
                    )
            if len(detecting_boundaries) > i + 1:
                my_dict["FPs"].append(
                    times_pred[
                        (times_pred > detecting_boundaries[i][1])
                        & (times_pred < detecting_boundaries[i + 1][0])
                    ]
                )

        my_dict["FPs"].append(times_pred[times_pred > detecting_boundaries[i][1]])
    else:
        my_dict["FPs"].append(times_pred)

    if len(my_dict["FPs"]) > 1:
        my_dict["FPs"] = np.concatenate(my_dict["FPs"])
    elif len(my_dict["FPs"]) == 1:
        my_dict["FPs"] = my_dict["FPs"][0]
    if len(my_dict["FPs"]) == 0:
        my_dict["FPs"] = []

    if binary:
        if len(my_dict["FNs"]) > 1:
            my_dict["FNs"] = np.concatenate(my_dict["FNs"])
        elif len(my_dict["FNs"]) == 1:
            my_dict["FNs"] = my_dict["FNs"][0]
        if len(my_dict["FNs"]) == 0:
            my_dict["FNs"] = []
    return my_dict


def confusion_matrix(true, prediction):
    true_ = true == 1
    prediction_ = prediction == 1
    TP = (true_ & prediction_).sum()
    TN = (~true_ & ~prediction_).sum()
    FP = (~true_ & prediction_).sum()
    FN = (true_ & ~prediction_).sum()
    return TP, TN, FP, FN


def single_average_delay(
    detecting_boundaries,
    prediction,
    anomaly_window_destination,
    clear_anomalies_mode,
):
    detecting_boundaries = filter_detecting_boundaries(detecting_boundaries)
    point = 0 if clear_anomalies_mode else -1
    dict_cp_confusion = extract_cp_confusion_matrix(
        detecting_boundaries, prediction, point=point
    )

    missing = 0
    detectHistory = []
    all_true_anom = 0
    FP = 0

    FP += len(dict_cp_confusion["FPs"])
    missing += len(dict_cp_confusion["FNs"])
    all_true_anom += len(dict_cp_confusion["TPs"]) + len(
        dict_cp_confusion["FNs"]
    )

    if anomaly_window_destination == "lefter":

        def average_time(output_cp_cm_tp):
            return output_cp_cm_tp[2] - output_cp_cm_tp[1]

    elif anomaly_window_destination == "righter":

        def average_time(output_cp_cm_tp):
            return output_cp_cm_tp[1] - output_cp_cm_tp[0]

    elif anomaly_window_destination == "center":

        def average_time(output_cp_cm_tp):
            return output_cp_cm_tp[1] - (
                output_cp_cm_tp[0]
                + (output_cp_cm_tp[2] - output_cp_cm_tp[0]) / 2
            )

    else:
        raise Exception("Choose anomaly_window_destination")

    for fp_case_window in dict_cp_confusion["TPs"]:
        detectHistory.append(average_time(dict_cp_confusion["TPs"][fp_case_window]))
    return missing, detectHistory, FP, all_true_anom


def my_scale(
    fp_case_window=None,
    A_tp=1,
    A_fp=0,
    koef=1,
    detalization=1000,
    clear_anomalies_mode=True,
    plot_figure=False,
):
    x = np.linspace(-np.pi / 2, np.pi / 2, detalization)
    x = x if clear_anomalies_mode else x[::-1]
    y = (
        (A_tp - A_fp)
        / 2
        * -1
        * np.tanh(koef * x)
        / (np.tanh(np.pi * koef / 2))
        + (A_tp - A_fp) / 2
        + A_fp
    )
    if not plot_figure and fp_case_window is not None:
        event = int(
            (fp_case_window[1] - fp_case_window[0])
            / (fp_case_window[-1] - fp_case_window[0])
            * detalization
        )
        if event >= len(x):
            event = len(x) - 1
        score = y[event]
        return score
    return y


def single_evaluate_nab(
    detecting_boundaries,
    prediction,
    table_of_coef=None,
    clear_anomalies_mode=True,
    scale_func="improved",
    scale_koef=1,
):
    if scale_func == "improved":
        scale_func = my_scale
    else:
        raise Exception("choose the scale_func")

    detecting_boundaries = filter_detecting_boundaries(detecting_boundaries)

    if table_of_coef is None:
        table_of_coef = pd.DataFrame(
            [
                [1.0, -0.11, 1.0, -1.0],
                [1.0, -0.22, 1.0, -1.0],
                [1.0, -0.11, 1.0, -2.0],
            ]
        )
        table_of_coef.index = pd.Index(["Standard", "LowFP", "LowFN"])
        table_of_coef.index.name = "Metric"
        table_of_coef.columns = ["A_tp", "A_fp", "A_tn", "A_fn"]

    point = 0 if clear_anomalies_mode else -1
    dict_cp_confusion = extract_cp_confusion_matrix(
        detecting_boundaries, prediction, point=point
    )

    scores, scores_perfect, scores_null = [], [], []
    for profile in ["Standard", "LowFP", "LowFN"]:
        A_tp = table_of_coef["A_tp"][profile]
        A_fp = table_of_coef["A_fp"][profile]
        A_fn = table_of_coef["A_fn"][profile]

        score = 0
        score += A_fp * len(dict_cp_confusion["FPs"])
        score += A_fn * len(dict_cp_confusion["FNs"])
        for fp_case_window in dict_cp_confusion["TPs"]:
            set_times = dict_cp_confusion["TPs"][fp_case_window]
            score += scale_func(set_times, A_tp, A_fp, koef=scale_koef)

        scores.append(score)
        scores_perfect.append(len(detecting_boundaries) * A_tp)
        scores_null.append(len(detecting_boundaries) * A_fn)

    return np.array(
        [np.array(scores), np.array(scores_null), np.array(scores_perfect)]
    )


def chp_score(
    true,
    prediction,
    metric="nab",
    window_width=None,
    portion=0.1,
    anomaly_window_destination="lefter",
    clear_anomalies_mode=True,
    intersection_mode="cut right window",
    table_of_coef=None,
    scale_func="improved",
    scale_koef=1,
    plot_figure=False,
    verbose=True,
):
    assert isinstance(true, pd.Series) or isinstance(true, list)

    if isinstance(prediction, pd.Series):
        true = [true]
        prediction = [prediction]
    elif isinstance(prediction, list):
        if not all(isinstance(my_el, pd.Series) for my_el in prediction):
            raise Exception("Incorrect format for prediction")
    else:
        raise Exception("Incorrect format for prediction")

    assert len(true) == len(prediction)
    input_variant = check_errors(true)

    def check_sort(my_list, variant):
        for dataset in my_list:
            if variant == 2:
                assert all(np.sort(dataset) == np.array(dataset))
            elif variant == 3:
                assert all(
                    np.sort(np.concatenate(dataset)) == np.concatenate(dataset)
                )
            elif variant == 1:
                assert all(
                    dataset.index.values == dataset.sort_index().index.values
                )

    check_sort(true, input_variant)
    check_sort(prediction, 1)

    if (
        ((metric == "nab") or (metric == "average_time"))
        and (window_width is None)
        and (input_variant != 3)
    ):
        print(
            f"Since you didn't choose window_width and portion, portion will be default ({portion})"
        )

    if input_variant == 1:
        detecting_boundaries = [
            single_detecting_boundaries(
                true_series=true[i],
                true_list_ts=None,
                prediction=prediction[i],
                window_width=window_width,
                portion=portion,
                anomaly_window_destination=anomaly_window_destination,
                intersection_mode=intersection_mode,
            )
            for i in range(len(true))
        ]
    elif input_variant == 2:
        detecting_boundaries = [
            single_detecting_boundaries(
                true_series=None,
                true_list_ts=true[i],
                prediction=prediction[i],
                window_width=window_width,
                portion=portion,
                anomaly_window_destination=anomaly_window_destination,
                intersection_mode=intersection_mode,
            )
            for i in range(len(true))
        ]
    elif input_variant == 3:
        detecting_boundaries = true.copy()
        for i in range(len(detecting_boundaries)):
            if len(detecting_boundaries[i]) == 0:
                detecting_boundaries[i] = [[]]
    else:
        raise Exception("Unknown format for true data")

    if plot_figure:
        num_datasets = len(true)
        if ((metric == "binary") or (metric == "confusion_matrix")) and (
            input_variant == 1
        ):
            f = plt.figure(figsize=(16, 5 * num_datasets))
            grid = gridspec.GridSpec(num_datasets, 1)
            for i in range(num_datasets):
                globals()["ax" + str(i)] = f.add_subplot(grid[i])
                prediction[i].plot(
                    ax=globals()["ax" + str(i)], label="pred", marker="o"
                )
                true[i].plot(ax=globals()["ax" + str(i)], label="true", marker="o")
                globals()["ax" + str(i)].legend()
            plt.show()
        else:
            f = plt.figure(figsize=(16, 5 * num_datasets))
            grid = gridspec.GridSpec(num_datasets, 1)
            detalization = 100
            for i in range(num_datasets):
                globals()["ax" + str(i)] = f.add_subplot(grid[i])
                print_legend_boundary = True

                def plot_cp(couple, destination, ax, label):
                    if destination == "lefter":
                        ax.axvline(couple[1], c="r", label=label)
                    elif destination == "righter":
                        ax.axvline(couple[0], c="r", label=label)
                    elif destination == "center":
                        ax.axvline(
                            couple[0] + ((couple[1] - couple[0]) / 2),
                            c="r",
                            label=label,
                        )

                for couple in detecting_boundaries[i]:
                    if len(couple) > 0:
                        globals()["ax" + str(i)].axvspan(
                            couple[0],
                            couple[1],
                            alpha=0.5,
                            color="green",
                            label="detection \nboundary"
                            if print_legend_boundary
                            else None,
                        )
                        nab = pd.Series(
                            my_scale(plot_figure=True, detalization=detalization),
                            index=pd.date_range(
                                couple[0], couple[1], periods=detalization
                            ),
                        )
                        nab.plot(
                            ax=globals()["ax" + str(i)],
                            linewidth=0.4,
                            color="brown",
                            label="nab scoring func"
                            if print_legend_boundary
                            else None,
                        )
                        plot_cp(
                            couple,
                            anomaly_window_destination,
                            globals()["ax" + str(i)],
                            label="Changepoint"
                            if print_legend_boundary
                            else None,
                        )
                        print_legend_boundary = False
                prediction[i].plot(
                    ax=globals()["ax" + str(i)], label="pred", marker="o"
                )
                globals()["ax" + str(i)].legend()
            plt.show()

    if metric == "nab":
        matrix = np.zeros((3, 3))
        for i in range(len(prediction)):
            matrix_ = single_evaluate_nab(
                detecting_boundaries[i],
                prediction[i],
                table_of_coef=table_of_coef,
                clear_anomalies_mode=clear_anomalies_mode,
                scale_func=scale_func,
                scale_koef=scale_koef,
            )
            matrix = matrix + matrix_

        results = {}
        desc = ["Standard", "LowFP", "LowFN"]
        for t, profile_name in enumerate(desc):
            results[profile_name] = round(
                100
                * (matrix[0, t] - matrix[1, t])
                / (matrix[2, t] - matrix[1, t]),
                2,
            )
            if verbose:
                print(profile_name, " - ", results[profile_name])
        return results

    elif metric == "average_time":
        missing, detect_history, fp, all_true_anom = 0, [], 0, 0
        for i in range(len(prediction)):
            missing_, detect_history_, fp_, all_true_anom_ = single_average_delay(
                detecting_boundaries[i],
                prediction[i],
                anomaly_window_destination=anomaly_window_destination,
                clear_anomalies_mode=clear_anomalies_mode,
            )
            missing += missing_
            detect_history += detect_history_
            fp += fp_
            all_true_anom += all_true_anom_
        add = np.mean(detect_history)
        if verbose:
            print("Amount of true anomalies", all_true_anom)
            print(f"A number of missed CPs = {missing}")
            print(f"A number of FPs = {int(fp)}")
            print("Average time", add)
        return add, missing, int(fp), all_true_anom

    elif (metric == "binary") or (metric == "confusion_matrix"):
        if all(isinstance(my_el, pd.Series) for my_el in true):
            TP, TN, FP, FN = 0, 0, 0, 0
            for i in range(len(prediction)):
                TP_, TN_, FP_, FN_ = confusion_matrix(true[i], prediction[i])
                TP, TN, FP, FN = TP + TP_, TN + TN_, FP + FP_, FN + FN_
        else:
            print(
                "For this metric it is better if you use pd.Series format for true \nwith common index of true and prediction"
            )
            TP, TN, FP, FN = 0, 0, 0, 0
            for i in range(len(prediction)):
                dict_cp_confusion = extract_cp_confusion_matrix(
                    detecting_boundaries[i], prediction[i], binary=True
                )
                TP += np.sum(
                    [
                        len(dict_cp_confusion["TPs"][window][1])
                        for window in dict_cp_confusion["TPs"]
                    ]
                )
                FP += len(dict_cp_confusion["FPs"])
                FN += len(dict_cp_confusion["FNs"])
                TN += len(prediction[i]) - TP - FP - FN

        if metric == "binary":
            f1 = round(TP / (TP + (FN + FP) / 2), 2)
            far = round(FP / (FP + TN) * 100, 2)
            mar = round(FN / (FN + TP) * 100, 2)
            if verbose:
                print(f"False Alarm Rate {far} %")
                print(f"Missing Alarm Rate {mar} %")
                print(f"F1 metric {f1}")
            return f1, far, mar

        if verbose:
            print("TP", TP)
            print("TN", TN)
            print("FP", FP)
            print("FN", FN)
        return TP, TN, FP, FN
    else:
        raise Exception("Choose the performance metric")
