aerial_gym_dev_path="/home/paran/Dropbox/aerial_gym_dev/aerial_gym_dev"
import sys
import isaacgym
sys.path.append(aerial_gym_dev_path)
import numpy as np
from aerial_gym_dev import AERIAL_GYM_ROOT_DIR
file_path = AERIAL_GYM_ROOT_DIR + "/resources/robots/generalized_aerial_robot/generalized_model_wrench.urdf"
from aerial_gym_dev.utils.urdf_creator import create_urdf_from_model
import aerial_gym_dev.envs.base.generalized_aerial_robot_config 
import aerial_gym_dev.envs.base.generalized_aerial_robot
from aerial_gym_dev.utils.task_registry import task_registry
from aerial_gym_dev.utils import get_args, task_registry
import torch
import problem_airframes

def target_LQR_control(robot_model, target):


    assert type(target)==list
    assert len(target)==3

    del sys.modules['aerial_gym_dev.envs.base.generalized_aerial_robot_config']
    del sys.modules['aerial_gym_dev.envs.base.generalized_aerial_robot']
    import aerial_gym_dev.envs.base.generalized_aerial_robot_config 
    import aerial_gym_dev.envs.base.generalized_aerial_robot

    aerial_gym_dev.envs.base.generalized_aerial_robot_config.robot_model = robot_model
    aerial_gym_dev.envs.base.generalized_aerial_robot_config.GenAerialRobotCfg.robot_asset.robot_model = robot_model


    task_registry.register("gen_aerial_robot", aerial_gym_dev.envs.base.generalized_aerial_robot.GenAerialRobot, aerial_gym_dev.envs.base.generalized_aerial_robot_config.GenAerialRobotCfg())

    args = get_args()
    args.num_envs = 1
    args.task = 'gen_aerial_robot'
    args.headless = True

    env, env_cfg = task_registry.make_env(name=args.task, args=args)
    assert env_cfg.control.controller == "LQR_control"
    env_cfg.num_actions = 12
    
    env.reset()
    command_actions = torch.tensor(target+[0.,0.,0.7,0.,0.,0.,0.,0.,0.], dtype=torch.float32)
    command_actions = command_actions.reshape((1,env_cfg.control.num_actions))
    command_actions = command_actions.repeat(env_cfg.env.num_envs,1)
    _, _, _, _, _ = env.step(command_actions)
    env.reset()



    command_actions = torch.tensor(target+[0.,0.,0.7,0.,0.,0.,0.,0.,0.], dtype=torch.float32)
    command_actions = command_actions.reshape((1,env_cfg.control.num_actions))
    command_actions = command_actions.repeat(env_cfg.env.num_envs,1)
    
    
    episode_length = 300
    reward_list = []
    obs_list = []
    for i in range(0, episode_length):
        obs, priviliged_obs, rewards, resets, extras = env.step(command_actions)

        if bool(resets.cpu()[0]): # stop if the airframe is reinitialized
            break

        # env.render()
        r = rewards[0].item()
        pose = np.array(obs['obs'].cpu())[0][0:7]
        reward_list.append(r)
        obs_list.append(pose)

    env.reset()
    return np.array(reward_list), np.array(obs_list)


if __name__ == '__main__':
    import sys
    assert len(sys.argv) == 3
    target = eval(sys.argv[2])
    pars = problem_airframes._decode_symmetric_hexarotor_to_RobotParameter(np.array(eval(sys.argv[1])))
    res = target_LQR_control(problem_airframes.RobotModel(pars), target)
    print("result:")
    print(res[0].tolist())
    print(res[1].tolist())