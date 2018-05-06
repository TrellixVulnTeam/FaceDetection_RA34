import mxnet as mx
import numpy as np
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def upsample_filt(size):
    factor = (size + 1) // 2
    if size % 2 == 1:
        center = factor - 1
    else:
        center = factor - 0.5
    og = np.ogrid[:size, :size]
    return (1 - abs(og[0] - center) / factor) * \
           (1 - abs(og[1] - center) / factor)


def load_param(ctx, rpn_symbol, vgg16fc_args, vgg16fc_auxs,load_after_vgg= 1,load_after_proposal=0):
    fc_args = vgg16fc_args.copy()
    fc_auxs = vgg16fc_auxs.copy()

    for k, v in fc_args.items():
        if v.context != ctx:
            fc_args[k] = mx.nd.zeros(v.shape, ctx)
            v.copyto(fc_args[k])

    for k, v in fc_auxs.items():
        if v.context != ctx:
            fc_auxs[k] = mx.nd.zeros(v.shape, ctx)
            v.copyto(fc_auxs[k])

    data_shape = (1, 3, 600, 600)
    proj_label = (128, 128, 10, 2)
    ground_truth = (10,2)
    ellipse_label = (10,5)
    arg_names = rpn_symbol.list_arguments()
    aux_names = rpn_symbol.list_auxiliary_states()
    #
    # arg_shapes, _, aux_shapes = rpn_symbol.infer_shape(data=data_shape , mean_face=(10, 3),proj_label=proj_label,
    #                                                         ground_truth =ground_truth, ellipse_label = ellipse_label)


    arg_shapes, _, aux_shapes = rpn_symbol.infer_shape(data=data_shape , mean_face=(10, 3),proj_label=proj_label)
    # arg_shapes, _, aux_shapes = rpn_symbol.infer_shape(data=data_shape )

    fc_auxs = {k: mx.nd.zeros(s, ctx) for k, s in zip(aux_names, aux_shapes)}

    fresh_initilization_list = []
    if load_after_vgg :
        fresh_initilization_list = ['roi_warping_fc1_weight', 'roi_warping_fc1_bias',
                        'roi_warping_fc2_weight', 'roi_warping_fc2_bias',
                        'offset_predict_weight', 'offset_predict_bias',
                        'conv_proposal_weight','conv_proposal_bias',
                        'proposal_cls_score_weight', 'proposal_cls_score_bias',
                        'param3d_pred_weight', 'param3d_pred_bias']
    if load_after_proposal:
        fresh_initilization_list = ['roi_warping_fc1_weight', 'roi_warping_fc1_bias',
                        'roi_warping_fc2_weight', 'roi_warping_fc2_bias',
                        'offset_predict_weight', 'offset_predict_bias']

    for name, shape in zip(arg_names, arg_shapes):
        if name in fresh_initilization_list:
            fan_in, fan_out = np.prod(shape[1:]), shape[0]
            factor = fan_in
            scale = np.sqrt(2.34 / factor)
            tempt = np.random.uniform(-scale, scale, size=shape)
            fc_args[name] = mx.nd.array(tempt, ctx)
        elif name in ['roi_warping_bn1_gamma', 'roi_warping_bn2_gamma']:
            fc_args[name] = mx.nd.ones(shape, ctx)
        elif name in ['roi_warping_bn1_beta', 'roi_warping_bn2_beta']:
            fc_args[name] = mx.nd.zeros(shape, ctx)

    deconv_params = dict([(x[0], x[1]) for x in zip(arg_names, arg_shapes)
                          if x[0] in ["upsample_proposal_weight"]])
    for k, v in deconv_params.items():
        filt = upsample_filt(v[3])
        initw = np.zeros(v)
        initw[range(v[0]), range(v[1]), :, :] = filt  # be careful here is the slice assing
        fc_args[k] = mx.nd.array(initw, ctx)

    return fc_args, fc_auxs
