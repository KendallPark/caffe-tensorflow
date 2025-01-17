import math
from collections import namedtuple

from .errors import KaffeError

TensorShape = namedtuple('TensorShape', ['batch_size', 'channels', 'height', 'width'])


def get_filter_output_shape_fn(round_func, dilation = 1):
    def get_filter_output_shape(i_h, i_w, params):
        effective_pad_h = params.pad_h / dilation
        effective_pad_w = params.pad_w / dilation
        o_h = (i_h + 2 * effective_pad_h - params.kernel_h) / float(params.stride_h) + 1
        o_w = (i_w + 2 * effective_pad_w - params.kernel_w) / float(params.stride_w) + 1
        return (int(round_func(o_h)), int(round_func(o_w)))
    return get_filter_output_shape

def get_upsampling_output_shape(i_h, i_w, params):
    o_h = (i_h - 1) * params.stride_h - 2 * params.pad_h + params.kernel_h
    o_w = (i_w - 1) * params.stride_w - 2 * params.pad_w + params.kernel_w
    return o_h, o_w

def get_strided_kernel_output_shape(node, output_shape_func):
    assert node.layer is not None
    input_shape = node.get_only_parent().output_shape
    o_h, o_w = output_shape_func(input_shape.height, input_shape.width,
                                 node.layer.kernel_parameters)
    params = node.layer.parameters
    has_c_o = hasattr(params, 'num_output')
    c = params.num_output if has_c_o else input_shape.channels
    return TensorShape(input_shape.batch_size, c, o_h, o_w)


def shape_not_implemented(node):
    raise NotImplementedError  


def shape_identity(node):
    assert len(node.parents) > 0
    return node.parents[0].output_shape


def shape_scalar(node):
    return TensorShape(1, 1, 1, 1)


def shape_data(node):
    if node.output_shape:
        # Old-style input specification
        val = node.output_shape
        if len(val) < 4:
            return list(val) + [1] * (4 - len(val))
        return val
    try:
        # New-style input specification
        return map(int, node.parameters.shape[0].dim)
    except:
        # We most likely have a data layer on our hands. The problem is,
        # Caffe infers the dimensions of the data from the source (eg: LMDB).
        # We want to avoid reading datasets here. Fail for now.
        # This can be temporarily fixed by transforming the data layer to
        # Caffe's "input" layer (as is usually used in the "deploy" version).
        # TODO: Find a better solution for this.
        raise KaffeError('Cannot determine dimensions of data layer.\n'
                         'See comments in function shape_data for more info.')

def shape_reshape(node):
    dims = node.parameters.shape.dim
    return TensorShape(dims[0], dims[1], dims[2], dims[3])

def shape_mem_data(node):
    params = node.parameters
    return TensorShape(params.batch_size, params.channels, params.height, params.width)


def shape_concat(node):
    axis = node.layer.parameters.axis
    output_shape = None
    for parent in node.parents:
        if output_shape is None:
            output_shape = list(parent.output_shape)
        else:
            output_shape[axis] += parent.output_shape[axis]
    return tuple(output_shape)

def reshape_shape(node) :
    
    input_shape = node.get_only_parent().output_shape
    input_shape_pr = input_shape.channels*input_shape.height*input_shape.width
    input_shape_arr = [input_shape.batch_size,input_shape.channels,input_shape.height,input_shape.width]
    pr = 1
    axes = node.parameters.shape.dim
    new_shape = [input_shape.batch_size,1,1,1]
    for j in range(1,len(axes)) :
        if axes[j] == 0 :
            new_shape[j] = input_shape_arr[j]
            pr *= new_shape[j]
        elif not axes[j] == -1 :
            new_shape[j] = int(axes[j])
            pr *= new_shape[j]
        elif axes[j] == -1 :
            new_shape[j] = -1

    for j in range(1,len(new_shape)) :
        if new_shape[j] == -1 :
            new_shape[j] = int(input_shape_pr/pr)

    return TensorShape(new_shape[0],new_shape[1],new_shape[2],new_shape[3])                

def flatten_shape(node) :
    shape1 = node.get_only_parent().output_shape
    
    return TensorShape(shape1.batch_size,shape1.channels*shape1.height*shape1.width,1,1)
    
def shape_convolution(node):
    dilation = node.layer.get_kernel_value(None, node.parameters.dilation, 0, default = 1)
    return get_strided_kernel_output_shape(node, get_filter_output_shape_fn(math.floor, dilation))

def shape_deconvolution(node):
    return get_strided_kernel_output_shape(node, get_upsampling_output_shape)

def shape_pool(node):
    return get_strided_kernel_output_shape(node, get_filter_output_shape_fn(math.ceil))


def shape_inner_product(node):
    input_shape = node.get_only_parent().output_shape
    return TensorShape(input_shape.batch_size, node.layer.parameters.num_output, 1, 1)
