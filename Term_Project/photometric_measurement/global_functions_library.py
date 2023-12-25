import matplotlib
import matplotlib.pyplot as plt
import numpy             as np

from astropy.io            import fits
from astropy.stats         import sigma_clip
from astropy.visualization import simple_norm

def plot_image(image_array: np.array, ax: matplotlib.axes._axes.Axes, v_min:np.float64, v_max: np.float64, cmap: str, norm_type: str, title: str, save_fig_flag: bool=False, save_file_path: str="./", save_dpi: np.int32=512, save_fig_name:str="image"):
    norm         = simple_norm(image_array, stretch=norm_type, percent=100.)
    ax.imshow(image_array, origin='lower', vmin=v_min, vmax=v_max, cmap=cmap)
    ax.axis("off")
    ax.set_title(title, fontsize=12., weight="bold")
    if save_fig_flag:
        save_file_path = "./"
        plt.savefig("%s/%s.png"%(save_file_path,save_fig_name), bbox_inches='tight', dpi=save_dpi, pad_inches=0.02, facecolor='white', transparent=True)
        
def make_mask_and_compute_background_statistics(imag_array: np.array, object_center_pos_pixel: np.array, crop_size: np.float64, object_circle_radius: np.float64, background_circle_radius: np.float64, how_many_sigma: np.float64, max_iter_criteria: np.float64, pixel_flux_weighted:bool=True) -> tuple:
    crop_left_edge, crop_right_edge           = np.int32(object_center_pos_pixel[1]) - crop_size, np.int32(object_center_pos_pixel[1]) + crop_size
    crop_down_edge, crop_up_edge              = np.int32(object_center_pos_pixel[0]) - crop_size, np.int32(object_center_pos_pixel[0]) + crop_size
    object_crop_center_pos_pixel              = np.array([object_center_pos_pixel[0]-crop_down_edge, object_center_pos_pixel[1]-crop_left_edge])

    # crop the image
    imag_data_crop                            = imag_array[crop_left_edge:crop_right_edge+1, crop_down_edge:crop_up_edge+1]
    clipped_result                            = sigma_clip(imag_data_crop, sigma=how_many_sigma, maxiters=max_iter_criteria, masked=True)

    # make object and background masks for the crop image
    x, y                                      = np.ogrid[0:imag_data_crop.shape[1],0:imag_data_crop.shape[0]][::-1]
    object_mask                               = ( (x-object_crop_center_pos_pixel[0])**2. + (y-object_crop_center_pos_pixel[1])**2.0 <= object_circle_radius**2.0 )
    background_mask                           = ( (x-object_crop_center_pos_pixel[0])**2. + (y-object_crop_center_pos_pixel[1])**2.0 > object_circle_radius**2.0 )\
                                              & ( (x-object_crop_center_pos_pixel[0])**2. + (y-object_crop_center_pos_pixel[1])**2.0 <= background_circle_radius**2.0 )

    # compute mean background signal
    mask_clipped                              = ( clipped_result.mask | (object_mask) )           # combine the sigma clipped and target masking

    data_background                           = imag_data_crop[~mask_clipped & background_mask]   # background are those pixels not clipped out (i.e., not bright sources or not target) and is in the backgroundmas
    background_pixel_count                    = (~mask_clipped & background_mask).sum()
    background_brightness_mean                = data_background.mean()

    # use pixels flux weighted coordinate as real center (we need to subtract the background noise to make the weighting more accurate)
    if pixel_flux_weighted:
        xx, yy                                    = np.meshgrid(np.arange(imag_data_crop.shape[0]), np.arange(imag_data_crop.shape[1]), indexing="xy")
        weighting                                 = imag_data_crop[object_mask]-background_brightness_mean
        weighting                                /= weighting.sum()
        object_crop_center_pos_pixel_weighted_x   = (xx[object_mask]*weighting).sum()
        object_crop_center_pos_pixel_weighted_y   = (yy[object_mask]*weighting).sum()
        object_crop_center_pos_pixel_weighted     = np.array([object_crop_center_pos_pixel_weighted_x, object_crop_center_pos_pixel_weighted_y])
    
        # remake object and background masks for the crop image
        object_mask                               = ( (x-object_crop_center_pos_pixel_weighted[0])**2. + (y-object_crop_center_pos_pixel_weighted[1])**2.0 <= object_circle_radius**2.0 )
        background_mask                           = ( (x-object_crop_center_pos_pixel_weighted[0])**2. + (y-object_crop_center_pos_pixel_weighted[1])**2.0 >  object_circle_radius**2.0 )\
                                                  & ( (x-object_crop_center_pos_pixel_weighted[0])**2. + (y-object_crop_center_pos_pixel_weighted[1])**2.0 <= background_circle_radius**2.0 )
                                          
        # redo background statistics
        mask_clipped                              = ( clipped_result.mask | (object_mask) )           # combine the sigma clipped and target masking

        data_background                           = imag_data_crop[~mask_clipped & background_mask]   # background are those pixels not clipped out (i.e., not bright sources or not target) and is in the backgroundmas
        background_pixel_count                    = (~mask_clipped & background_mask).sum()
        background_brightness_mean                = data_background.mean()
    
    background_brightness_std                 = data_background.std()
    background_brightness_mean_error          = background_brightness_std/background_pixel_count**0.5
    
    if pixel_flux_weighted:
        return imag_data_crop, mask_clipped, object_mask, background_mask, object_crop_center_pos_pixel_weighted, background_pixel_count, background_brightness_mean, background_brightness_mean_error, background_brightness_std 
    else:
        return imag_data_crop, mask_clipped, object_mask, background_mask, object_crop_center_pos_pixel,          background_pixel_count, background_brightness_mean, background_brightness_mean_error, background_brightness_std

def do_aperture_photometric_by_peak_brightness(imag_array: np.array, object_mask: np.array, aperture_threshold_array: np.array, background_brightness_mean: np.float64, background_brightness_mean_error: np.float64, background_brightness_std: np.float64, verbose: bool=False) -> tuple:
    data_object                                = imag_array[object_mask]
    data_object                               -= background_brightness_mean   # subtract the background noise 
    brightness_peak                            = data_object.max()
    
    aperture_mask_list                         = []
    aperture_pixel_count_array                 = []
    brightness_sum_within_aperture_array       = []
    brightness_sum_error_within_aperture_array = []
    
    for threshold in aperture_threshold_array:
        aperture_criteria                      = threshold*brightness_peak
        aperture_mask                          = (data_object >= aperture_criteria)
        aperture_pixel_count                   = aperture_mask.sum()
        brightness_sum_within_aperture         = data_object[aperture_mask].sum()
        brightness_sum_error_within_aperture   = (  brightness_sum_within_aperture/background_brightness_mean*background_brightness_std**2.\
                                                + aperture_pixel_count*background_brightness_std**2.\
                                                + aperture_pixel_count**2.*background_brightness_mean_error**2.)**0.5  # sum up contribution from source Poisson noise, background Poisson noise and error of the mean background brightness (since we subtract this value)
        aperture_mask_list.append(aperture_mask.copy())
        aperture_pixel_count_array.append(aperture_pixel_count)
        brightness_sum_within_aperture_array.append(brightness_sum_within_aperture)
        brightness_sum_error_within_aperture_array.append(brightness_sum_error_within_aperture)
        
        if verbose:
            print("Aperture threshold = %.4e:"%threshold)
            print("\tPixel counts in the aperture mask is %d ."%aperture_pixel_count)
            print("\tTotal Brightness within the aperture mask is %.4e ± %.4e %s ."%(brightness_sum_within_aperture, brightness_sum_error_within_aperture, "UNIT"))
            print("-"*100)
        
    aperture_pixel_count_array                  = np.array(aperture_pixel_count_array)
    brightness_sum_within_aperture_array        = np.array(brightness_sum_within_aperture_array)
    brightness_sum_error_within_aperture_array  = np.array(brightness_sum_error_within_aperture_array)
    
    return aperture_mask_list, aperture_pixel_count_array, brightness_sum_within_aperture_array, brightness_sum_error_within_aperture_array, brightness_peak

def do_aperture_photometric_by_radius(imag_array: np.array, object_mask: np.array, aperture_radius_array: np.array, object_center_pos: np.array, background_brightness_mean: np.float64, background_brightness_mean_error: np.float64, background_brightness_std: np.float64, verbose: bool=False) -> tuple:
    data_object                                = imag_array[object_mask]
    data_object                               -= background_brightness_mean   # subtract the background noise
    xx, yy                                     = np.meshgrid(np.arange(imag_array.shape[0]), np.arange(imag_array.shape[1]), indexing="xy")
    
    aperture_mask_list                         = []
    aperture_pixel_count_array                 = []
    brightness_sum_within_aperture_array       = []
    brightness_sum_error_within_aperture_array = []

    for radius in aperture_radius_array:
        aperture_mask                          = ( (xx[object_mask]-object_center_pos[0])**2.0 + (yy[object_mask]-object_center_pos[1])**2.0 <= radius**2.0 )
        aperture_pixel_count                   = aperture_mask.sum()
        brightness_sum_within_aperture         = data_object[aperture_mask].sum()
        brightness_sum_error_within_aperture   = (  brightness_sum_within_aperture/background_brightness_mean*background_brightness_std**2.\
                                                  + aperture_pixel_count*background_brightness_std**2.\
                                                  + aperture_pixel_count**2.*background_brightness_mean_error**2.)**0.5  # sum up contribution from source Poisson noise, background Poisson noise and error of the mean background brightness (since we subtract this value)
        aperture_mask_list.append(aperture_mask.copy())
        aperture_pixel_count_array.append(aperture_pixel_count)
        brightness_sum_within_aperture_array.append(brightness_sum_within_aperture)
        brightness_sum_error_within_aperture_array.append(brightness_sum_error_within_aperture)
    
        if verbose:
            print("Aperture radius = %.2f:"%radius)
            print("\tPixel counts in the aperture mask is %d ."%aperture_pixel_count)
            print("\tTotal Brightness within the aperture mask is %.4e ± %.4e %s ."%(brightness_sum_within_aperture, brightness_sum_error_within_aperture, "UNIT"))
            print("-"*100)
    
    aperture_pixel_count_array                  = np.array(aperture_pixel_count_array)
    brightness_sum_within_aperture_array        = np.array(brightness_sum_within_aperture_array)
    brightness_sum_error_within_aperture_array  = np.array(brightness_sum_error_within_aperture_array)
    
    return aperture_mask_list, aperture_pixel_count_array, brightness_sum_within_aperture_array, brightness_sum_error_within_aperture_array

def compute_instrumental_magnitude_and_error(pixel_brightness: np.float64, pixel_brightness_error: np.float64) -> tuple:
    m_inst       = -5.0/2.0*np.log10(pixel_brightness)
    m_inst_error =  5.0/(2.0*np.log(10))*(pixel_brightness_error/pixel_brightness)
    return m_inst, m_inst_error

def color_term_fitting(m_inst_lambda1: np.float64, m_inst_lambda2: np.float64, beta: np.float64, gamma: np.float64) -> np.float64:
    return m_inst_lambda1 + beta*(m_inst_lambda1-m_inst_lambda2) + gamma

def color_term_fitting_error(m_inst_lambda1: np.float64, m_inst_lambda2: np.float64, beta: np.float64, gamma: np.float64, m_inst_lambda1_error: np.float64, m_inst_lambda2_error: np.float64, beta_error: np.float64, gamma_error: np.float64) -> np.float64:
    return   (m_inst_lambda1_error**2.0\
            + ( beta*m_inst_lambda1_error)**2.0 + ( beta_error**m_inst_lambda1)**2.0\
            + (-beta*m_inst_lambda2_error)**2.0 + (-beta_error**m_inst_lambda2)**2.0\
            + gamma_error**2.0)**0.5

def residual_function(params: list, data: tuple) -> np.array:
    x_1, x_2, y, weight = data
    beta, gamma         = params[0], params[1]
    return ( y-color_term_fitting(m_inst_lambda1=x_1, m_inst_lambda2=x_2, beta=beta, gamma=gamma) )/weight  # Squaring will be taken by kmpfit function