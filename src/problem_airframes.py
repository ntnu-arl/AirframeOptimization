aerial_gym_dev_path="/home/paran/Dropbox/aerial_gym_dev/aerial_gym_dev"

import sys
import isaacgym
sys.path.append(aerial_gym_dev_path)
from aerial_gym_dev.envs import *
from aerial_gym_dev.utils import analyze_robot_config
from matplotlib import pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Line3D, Patch3D, Poly3DCollection, Text3D
from scipy.spatial.transform import Rotation
from aerial_gym_dev.envs.base.robot_model import RobotParameter, RobotModel
import numpy.typing
from tqdm import tqdm as tqdm
from math import sqrt
from matplotlib.animation import FuncAnimation
import subprocess

def from_0_1_to_RobotParameter(x: numpy.typing.NDArray[np.float_]):

    '''
    Every value in x is in the interval [0,1], where 0 represents lowest possible value, and 1 represents highest possible value.
    x = [
    [rx, ry, rz, theta1, theta2, theta3], # propeller 1
    [rx, ry, rz, theta1, theta2, theta3], # propeller 2
    etc.
    ]

    '''




    # A linear scalling to [0,1]^number_of_parameters
    assert type(x)==np.ndarray, "x = "+str(x)+" | type(x) = "+str(type(x))
    assert len(x.shape)==2 and x.shape[1] == 6, "x = "+str(x)
    n_rotors = x.shape[0]
    pars = RobotParameter

    
    pars.cq = 0.1
    pars.frame_mass = 0.5
    pars.motor_masses = [0.1] * n_rotors
    

    pars.motor_directions = ([1,-1,-1,1]*6)[:n_rotors]

    x_motor_translations = np.array([x[rotor_idx, i] for rotor_idx in range(n_rotors) for i in range(3)])
    x_motor_orientations = np.array([x[rotor_idx, i] for rotor_idx in range(n_rotors) for i in range(3,6)])

    pars.motor_translations = x_motor_translations.reshape(-1,3) * 2.0 - 1.0
    pars.motor_orientations = x_motor_orientations.reshape(-1, 3) * 360

    pars.motor_translations = pars.motor_translations.tolist()
    pars.motor_orientations = pars.motor_orientations.tolist()
    
    #pars.sensor_masses = [0.15, 0.1]
    #pars.sensor_orientations = [[0,0,0],[0,-20,0]]
    #pars.sensor_translations = [[0,0.5,0.1],[0,0,-0.1]]

    pars.max_u = 20
    pars.min_u = 0

    if True:
        with open('/home/paran/Dropbox/NTNU/11_constraints_encoding/code/robotConfigFile.txt','w') as f:
            print('pars.cq=',pars.cq, file=f, flush=True)
            print('pars.frame_mass=',pars.frame_mass, file=f)
            print('pars.motor_masses=',pars.motor_masses, file=f)

            print('pars.motor_translations=',pars.motor_translations, file=f)
            print('pars.motor_orientations=',pars.motor_orientations, file=f)
            print('pars.motor_directions=',pars.motor_directions, file=f)

            print('pars.max_u=',pars.max_u, file=f)
            print('pars.min_u=',pars.min_u, file=f)

    return pars

def constraint_check(pars: RobotParameter):
    robot = RobotModel(pars)
    check1, check2 = analyze_robot_config.analyze_robot_config(robot)
    return (check1, check2)

def _decode_symmetric_hexarotor_to_RobotParameter(x: numpy.typing.NDArray[np.float_]):

    # 5 parameters per rotor, 6 rotors in total. We only define 3 rotors, due to simmetry.
    assert x.shape == (5*3,) or x.shape == (5*2,), "x.shape = "+ str(x.shape)
    

    n_unique_rotors = round(x.shape[0]/5)
    euler_x_max_proportion = 0.2 # Maximum rotor inclination from vertical position. We dont want them to tilt more than 20%
    def scale_down_euler_x(euler_x_01):
        return euler_x_01*euler_x_max_proportion + (0.5 - euler_x_max_proportion/2.0)
    
    simmetry_plane = "y"


    x_decoded = np.zeros(shape=(2*n_unique_rotors,6), dtype=np.float64)
    # For each propeller, symmetric encoding has 5 parameters, and 0_1 encoding has 6 x 2 (one of the propellers has simmetric parameters).
    if simmetry_plane == "y":
        for prop_i in range(n_unique_rotors):
            # og
            x_decoded[prop_i*2, 0] = x[prop_i*5 +0]                          # r_x same
            x_decoded[prop_i*2, + 1] = x[prop_i*5 +1] / 2                    # r_y can only be in one side
            x_decoded[prop_i*2, + 2] = x[prop_i*5 +2]                        # r_z same
            x_decoded[prop_i*2, + 3] = scale_down_euler_x(x[prop_i*5 +3])      # euler_x same 
            x_decoded[prop_i*2, + 4] = 0.5                                   # euler_y constant (0.5)
            x_decoded[prop_i*2, + 5] = x[prop_i*5 +4]                        # euler_z same


            # symmetric
            x_decoded[prop_i*2+1, 0] = x[prop_i*5 +0]                        # r_x same
            x_decoded[prop_i*2+1, 1] = 1.0 - (x[prop_i*5 +1]/2)              # r_y inverse, and can only be in one side
            x_decoded[prop_i*2+1, 2] = x[prop_i*5 +2]                        # r_z same

            x_decoded[prop_i*2+1, 3] = scale_down_euler_x(1.0 - x[prop_i*5 +3])# euler_x inverse 
            x_decoded[prop_i*2+1, 4] = 0.5                                   # euler_y constant (0.5)
            x_decoded[prop_i*2+1, 5] = 1.0 - x[prop_i*5 +4]                  # euler_z inverse
    return from_0_1_to_RobotParameter(x_decoded)

def f_symmetric_hexarotor_0_1(x: numpy.typing.NDArray[np.float_], target):

    assert x.shape == (15,) or x.shape== (10,)

    target_str = '[' + ','.join([str(el) for el in target]) + ']'
    pars_str = '[' + ','.join([str(el) for el in x]) + ']'

    print("save parameters to robotConfigFile.txt")
    _decode_symmetric_hexarotor_to_RobotParameter(x)
    cmd_str = f"python src/airframes_objective_functions.py {target_str}"
    from datetime import datetime
    current_time = datetime.now()
    print(">>", cmd_str, current_time.strftime("%Y-%m-%d %H:%M:%S"))
    output = subprocess.check_output(cmd_str, shell=True, text=True)
    rewards = np.array(eval(output.split("result:")[-1].split("\n")[1]))
    poses = np.array(eval(output.split("result:")[-1].split("\n")[2]))

    f = 0
    for i, pose in enumerate(poses):
        distance = np.linalg.norm(np.array(target) - pose[0:3])
        f += distance / len(poses)
    
    f -= 100000 * (len(poses) - 300) # Bonus reward for episode length. Longer episode length means that evaluation was not prematurely terminated.
    return f, poses

def constraint_check_hexarotor_0_1(x: numpy.typing.NDArray[np.float_]):
    pars = _decode_symmetric_hexarotor_to_RobotParameter(x)
    return constraint_check(pars)

def plot_airframe_design(pars:RobotParameter, translation:numpy.typing.NDArray[np.float_]=np.zeros(3), rotation_matrix: numpy.typing.NDArray[np.float_]=np.eye(3,3), target=None):

    assert translation.shape==(3,)
    assert rotation_matrix.shape==(3,3)

    assert len(pars.motor_orientations) == len(pars.motor_translations)


    fig = plt.figure()
    xlim = ylim = zlim = [-1.2,3.2]
    ax = fig.add_subplot(projection='3d', xlim=xlim, ylim=ylim, zlim=zlim)
    ax.set_xlabel('x',size=18)
    ax.set_ylabel('y',size=18)
    ax.set_zlabel('z',size=18)
    
    _plot_airframe_into_ax(ax, pars, translation, rotation_matrix)
    if not target is None:
        ax.plot(*target, color='blue', marker='o')
    plt.show()

def _plot_airframe_into_ax(ax, pars:RobotParameter, translation, rotation_matrix):
    e1 = np.array([1,0,0])
    e2 = np.array([0,1,0])
    e3 = np.array([0,0,1])

    frame_scale_plane = 0.16
    frame_scale_normal = 0.26

    def apply_transformation(x, translation, rotation_matrix):
        assert x.shape == (3,)
        assert translation.shape == (3,)
        assert rotation_matrix.shape == (3,3)
        T = np.concatenate([rotation_matrix, translation.reshape(3,1)], axis=1)
        T = np.concatenate([T, np.array([[0,0,0,1]])])
        res = T@(np.array([x[0],x[1],x[2], 1]).T)
        return res.flatten()[0:3]

    for i in range(len(pars.motor_orientations)):
        t_vec = pars.motor_translations[i]
        R = Rotation.from_euler("xyz", pars.motor_orientations[i], degrees=True).as_matrix()
        if pars.motor_directions[i] == -1:
            color = "blue"
        elif pars.motor_directions[i] == 1:
            color = "orange"
        else:
            raise ValueError("Direction should be either 1 or -1. Instead, pars.motor_directions[i]=", pars.motor_directions[i])

        line_list = [
            [[0,t_vec[0]],[0,t_vec[1]],[0,t_vec[2]]],
            [[t_vec[0],t_vec[0]+R[0,:]@e1*frame_scale_plane],[t_vec[1],t_vec[1]+R[1,:]@e1*frame_scale_plane],[t_vec[2],t_vec[2]+R[2,:]@e1*frame_scale_plane]],
            [[t_vec[0],t_vec[0]+R[0,:]@e2*frame_scale_plane],[t_vec[1],t_vec[1]+R[1,:]@e2*frame_scale_plane],[t_vec[2],t_vec[2]+R[2,:]@e2*frame_scale_plane]],
            [[t_vec[0],t_vec[0]-R[0,:]@e1*frame_scale_plane],[t_vec[1],t_vec[1]-R[1,:]@e1*frame_scale_plane],[t_vec[2],t_vec[2]-R[2,:]@e1*frame_scale_plane]],
            [[t_vec[0],t_vec[0]-R[0,:]@e2*frame_scale_plane],[t_vec[1],t_vec[1]-R[1,:]@e2*frame_scale_plane],[t_vec[2],t_vec[2]-R[2,:]@e2*frame_scale_plane]],
            [[t_vec[0],t_vec[0]+R[0,:]@e3*frame_scale_normal],[t_vec[1],t_vec[1]+R[1,:]@e3*frame_scale_normal],[t_vec[2],t_vec[2]+R[2,:]@e3*frame_scale_normal]],
        ]

        color_list = ["gray"] + [color]*4 + ['g']
        for line, color in zip(line_list, color_list):
            start = np.array([line[0][0], line[1][0], line[2][0]])
            end = np.array([line[0][1], line[1][1], line[2][1]])
            start = apply_transformation(start, translation, rotation_matrix)
            end = apply_transformation(end, translation, rotation_matrix)
            ax.add_line(Line3D([start[0],end[0]],[start[1],end[1]],[start[2],end[2]], color=color))

def _plot_airframe_design_interactive(ax, params):

    og_pars = np.array([[el for el in params.values()]])
    pars = from_0_1_to_RobotParameter(og_pars)

    assert len(pars.motor_orientations) == len(pars.motor_translations)

    xlim = ylim = zlim = [-1.2,1.2]
    ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_zlim(zlim)

    ax.set_xlabel('x',size=18)
    ax.set_ylabel('y',size=18)
    ax.set_zlabel('z',size=18)
    
    e1 = np.array([1,0,0])
    e2 = np.array([0,1,0])
    e3 = np.array([0,0,1])

    frame_scale_plane = 0.16
    frame_scale_normal = 0.26

    for i in range(len(pars.motor_orientations)):
        t_vec = pars.motor_translations[i]
        R = Rotation.from_euler("xyz", pars.motor_orientations[i], degrees=True).as_matrix()
        if pars.motor_directions[i] == -1:
            color = "blue"
        elif pars.motor_directions[i] == 1:
            color = "orange"
        else:
            raise ValueError("Direction should be either 1 or -1. Instead, pars.motor_directions[i]=", pars.motor_directions[i])
        ax.add_line(Line3D([0,t_vec[0]],[0,t_vec[1]],[0,t_vec[2]]))
        ax.add_line(Line3D([t_vec[0],t_vec[0]+R[0,:]@e1*frame_scale_plane],[t_vec[1],t_vec[1]+R[1,:]@e1*frame_scale_plane],[t_vec[2],t_vec[2]+R[2,:]@e1*frame_scale_plane],color=color)) #x
        ax.add_line(Line3D([t_vec[0],t_vec[0]+R[0,:]@e2*frame_scale_plane],[t_vec[1],t_vec[1]+R[1,:]@e2*frame_scale_plane],[t_vec[2],t_vec[2]+R[2,:]@e2*frame_scale_plane],color=color)) #y
        ax.add_line(Line3D([t_vec[0],t_vec[0]-R[0,:]@e1*frame_scale_plane],[t_vec[1],t_vec[1]-R[1,:]@e1*frame_scale_plane],[t_vec[2],t_vec[2]-R[2,:]@e1*frame_scale_plane],color=color)) #x
        ax.add_line(Line3D([t_vec[0],t_vec[0]-R[0,:]@e2*frame_scale_plane],[t_vec[1],t_vec[1]-R[1,:]@e2*frame_scale_plane],[t_vec[2],t_vec[2]-R[2,:]@e2*frame_scale_plane],color=color)) #y
        ax.add_line(Line3D([t_vec[0],t_vec[0]+R[0,:]@e3*frame_scale_normal],[t_vec[1],t_vec[1]+R[1,:]@e3*frame_scale_normal],[t_vec[2],t_vec[2]+R[2,:]@e3*frame_scale_normal],color='g')) #z

def plot_airframe_interactive_single_rotor():
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, Slider

    print("--------------------------------------")
    print("-----Interactive Plot-----------------")
    print("The parameter 'euler y' is irrelevant.")
    print("--------------------------------------")

    params={
    'r1':0.5,
    'r2':0.5,
    'r3':0.5,
    'euler x':0.5,
    'euler y':0.5,
    'euler z':0.5,
    }

    # Create the figure and the line that we will manipulate
    fig = plt.figure()
    xlim = ylim = zlim = [-1.2,1.2]
    ax = fig.add_subplot(projection='3d', xlim=xlim, ylim=ylim, zlim=zlim)

    _plot_airframe_design_interactive(ax, params)

    # adjust the main plot to make room for the sliders
    fig.subplots_adjust(left=0.25, bottom=0.55)



    i = -1
    axes_list = []
    slider_list = []
    update_list = []


    def make_update(i):
        def update(val):
            key = list(params.keys())[i]
            ax.clear()
            params[key] = val
            _plot_airframe_design_interactive(ax, params)
            fig.canvas.draw_idle()
        return update


    for key, item in params.items():
        i += 1
        axes_list.append(fig.add_axes([0.25, 0.5*(9-i)/9, 0.65, 0.03]))
        slider_list.append(Slider(
            ax=axes_list[i],
            label=key,
            valmin=0.0,
            valmax=1.0,
            valinit=item,
        ))


        update_list.append(make_update(i))
        slider_list[-1].on_changed(update_list[-1])


    plt.show()

def animate_airframe(pars:RobotParameter, pose_list, target):


    fig = plt.figure()
    xlim = ylim = zlim = [-1.2,4.0]
    ax = fig.add_subplot(projection='3d', xlim=xlim, ylim=ylim, zlim=zlim)
    ax.set_xlabel('x',size=18)
    ax.set_ylabel('y',size=18)
    ax.set_zlabel('z',size=18)


    def animate(i):
        pose = pose_list[i]
        ax.clear()
        translation = pose[0:3]
        rotation_matrix = Rotation.from_euler("xyz", pose[3:6], degrees=False).as_matrix()
        _plot_airframe_into_ax(ax, pars, translation, rotation_matrix)
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_zlim(zlim)
        ax.set_xlabel(f'x={pose[0]:.2f}',size=14)
        ax.set_ylabel(f'y={pose[1]:.2f}',size=14)
        ax.set_zlabel(f'z={pose[2]:.2f}',size=14)
        ax.plot(*target, color="pink", marker="o")

    ani = FuncAnimation(fig, animate, frames=len(pose_list)-1, interval=100, repeat=False)
    plt.close()
    
    ani.save("test.gif", dpi=300)


if __name__ == "__main__":


    # # Single rotor interactive plot
    # plot_airframe_interactive_single_rotor()



    # # Plot hexarotor simmetric random drone, with 45 degree rotation and translation
    # rs = np.random.RandomState(5)
    # og_pars = rs.random(15)
    # decoded_pars = _decode_symmetric_hexarotor_to_RobotParameter(og_pars)
    # rotation_matrix = np.array([
    #     [1/sqrt(2) , -1/sqrt(2) , 0],
    #     [1/sqrt(2) , 1/sqrt(2) , 0],
    #     [0 , 0 , 1]
    # ])
    # translation = np.array([0.75,0,0])
    # plot_airframe_design(decoded_pars, translation, rotation_matrix)



    # target = [2.3,0.75,1.5]
    # target_str = '[' + ','.join([str(el) for el in target]) + ']'

    # rs = np.random.RandomState(5)
    # og_pars = rs.random(15)
    # pars_str = '[' + ','.join([str(el) for el in og_pars]) + ']'
    # output = subprocess.check_output(f"python src/airframes_objective_functions.py {pars_str} {target_str}", shell=True, text=True)
    # print(output.split("result:")[-1])

 
    # # Standard quad with LQR
    # print("the length of the arms increases over time??")
    # target = [2.3,0.75,1.5]
    # pars_0_1 = np.array(
    #     [[0.65 ,0.35,0.5,  0,0,0],
    #      [0.35,0.35,0.5, 0,0,0],
    #      [0.35,0.65 ,0.5,  0,0,0],
    #      [0.65 ,0.65 ,0.5,  0,0,0],
    #      [0.5 ,0.65 ,0.5,  0,0,0],
    #      [0.35 ,0.5 ,0.5,  0,0,0],])
    # pars:RobotParameter = from_0_1_to_RobotParameter(pars_0_1)
    # model = RobotModel(pars)
    # rewards, poses = target_LQR_control(model, target)
    # animate_airframe(pars, poses, target)

  


    # Analyze solutions

    target = [2.3,0.75,1.5]

    # Best solution
    x = np.array([0.49580943483950735, 0.8446168367709378, 0.7518539791904498, 0.13353196954967322, 0.6860072491492938, 0.9692333121269158, 0.5187270188694916, 0.550890465330575, 0.1443820822505597, 0.2227223052526963, 0.31845214783310405, 0.8595968832825416, 0.4364441257720804, 0.4042662014448113, 0.455128119397063])

    # # Quad
    # x = np.array([0.1465, 0.1465*2, 0.5, 0.5, 0.0,
    #               1.0-0.1465, 0.1465*2, 0.5, 0.5, 0.0,
    #             ])

    # Hex
    # x = np.array([0,1.0,0.5,0.5,0.0,1.0-np.cos(np.pi/3)/2,1.0-np.sin(np.pi/3),0.5,0.5,0.0,np.cos(np.pi/3)/2,1.0-np.sin(np.pi/3),0.5,0.5,0.0]); is_hex = True

    # pars.motor_translations = [[np.cos(np.pi / 3),-np.sin(np.pi / 3),0], [-np.cos(np.pi / 3),-np.sin(np.pi / 3),0], [-1.,0.,0], [-np.cos(np.pi / 3),np.sin(np.pi / 3) ,0], [np.cos(np.pi / 3),np.sin(np.pi / 3),0.], [1.,0.,0.]]

    print(constraint_check_hexarotor_0_1(x))
    plot_airframe_design(_decode_symmetric_hexarotor_to_RobotParameter(x), target=np.array(target))
    print("Constraints: ")
    [print("g(x) = ", el) for el in  constraint_check(_decode_symmetric_hexarotor_to_RobotParameter(x))]

    f, poses = f_symmetric_hexarotor_0_1(x, target)
    print(f)
    animate_airframe(_decode_symmetric_hexarotor_to_RobotParameter(x), poses, target)



    pass


# cd /home/paran/Dropbox/aerial_gym_dev/aerial_gym_dev/scripts
# python3 example_control.py --task=gen_aerial_robot --num_envs=1



















# # If I change these parameters, is that the full set of possible quad configurations?

# print(pars.motor_orientations) # [[0,365] x 3] x 4
# print(pars.motor_translations) # [[-1,1] x 3] x 4
# print(pars.motor_directions) # {-1,1} x 4


# # Is there a way to visualize the drones?

# change the parameters in envs/base/generalized_aerial_robot_config.py

# then run scripts/example_control.py

# plot mr design function, https://github.com/WilhelmWG/Evolutionary-Algorithm-for-Multirotor-Morphology-Search/blob/main/plotting.py

# # How do I get a feasability check? I am looking for a function with binary output.

# analyze_robot_config.analyze_robot_config(robot)


