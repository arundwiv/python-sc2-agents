#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Oliver Just-De Bleser
"""


from pysc2.agents import base_agent
from pysc2.lib import actions, features, units
import random
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from actor_critic import ActorCriticNetwork
import numpy as np
import matplotlib.pyplot as plt
import tensorflow_probability as tfp


class Agent(base_agent.BaseAgent):
    def __init__(self, alpha=1e-4, gamma=0.99, n_actions=11):
        super(Agent, self).__init__()
        self.gamma = gamma
        self.n_actions = n_actions
        self.action = None
        self.action_space = [i for i in range(self.n_actions)]
        self.actor_critic = ActorCriticNetwork(n_actions=n_actions)
        self.actor_critic.compile(optimizer=Adam(learning_rate=alpha))

    def choose_action(self, scalar_observations, spacial_observations):
        scalar_state = tf.convert_to_tensor([scalar_observations])
        spacial_state = tf.convert_to_tensor([spacial_observations], dtype=tf.float16)
        
        _, probs_action, x, y = self.actor_critic(scalar_state, spacial_state)
        print(probs_action)
        action_probabilities = tfp.distributions.Categorical(probs=probs_action)
        action = action_probabilities.sample()
        log_prob = action_probabilities.log_prob(action)
        self.action = action
        return action.numpy()[0], x, y
    
    def save_models(self):
        print('... saving models ...')
        self.actor_critic.save_weights(self.actor_critic.checkpoint_file)
    
    def load_models(self):
        print('... loading models ...')
        self.actor_critic.load_weights(self.actor_critic.checkpoint_file)
    
    def learn(self, state, reward, state_, done):
        pass
    
    def step(self, obs):
        super(Agent, self).step(obs)
        # creating our state space to feed to the a Neural network
        minerals = obs.observation.player.minerals
        food_used = obs.observation.player.food_used
        food_cap = obs.observation.player.food_cap
        supply_remaining = food_cap - food_used
        scvs_count = len([unit for unit in obs.observation['feature_units'] if unit.unit_type == units.Terran.SCV])
        marines_count = len([unit for unit in obs.observation['feature_units'] if unit.unit_type == units.Terran.Marine])
        barracks_count = len([unit for unit in obs.observation['feature_units'] if unit.unit_type == units.Terran.Barracks and unit.build_progress == 100])
        barracks_building = len([unit for unit in obs.observation['feature_units'] if unit.unit_type == units.Terran.Barracks and unit.build_progress < 100])
        sd_count = len([unit for unit in obs.observation['feature_units'] if unit.unit_type == units.Terran.SupplyDepot and unit.build_progress == 100])
        sd_building = len([unit for unit in obs.observation['feature_units'] if unit.unit_type == units.Terran.SupplyDepot and unit.build_progress < 100])

        scalar_observations = np.array([
            minerals,
            food_used,
            food_cap,
            supply_remaining,
            scvs_count,
            marines_count,
            barracks_count,
            barracks_building,
            sd_count,
            sd_building
        ])
        # Assuming obs is your current observation
        feature_screen = obs.observation['feature_screen']
        unit_type = np.array(feature_screen[features.SCREEN_FEATURES.unit_type.index])
        command_screen = (unit_type == units.Terran.CommandCenter).astype(int)
        marine_screen = (unit_type == units.Terran.Marine).astype(int)
        scv_screen = (unit_type == units.Terran.SCV).astype(int)
        mineral_screen = (unit_type == units.Neutral.MineralField).astype(int)
        barrack_screen = (unit_type == units.Terran.Barracks).astype(int)
        selected = np.array(feature_screen[features.SCREEN_FEATURES.selected.index])
        unit_density = np.array(feature_screen[features.SCREEN_FEATURES.unit_density.index])
        active = np.array(feature_screen[features.SCREEN_FEATURES.active.index])
        pathable = np.array(feature_screen[features.SCREEN_FEATURES.pathable.index])
        
        spacial_observations = np.stack([
            unit_type,
            command_screen,
            marine_screen,
            scv_screen,
            mineral_screen,
            barrack_screen,
            selected,
            unit_density,
            active,
            pathable
        ], axis=-1)
        
        
       
        print(self.choose_action(scalar_observations, spacial_observations))
        return actions.FUNCTIONS.no_op()

    def select_command(self, obs):
        commands = self.get_units_by_type(obs, units.Terran.CommandCenter)
        if len(commands) > 0:
            command = random.choice(commands)
            return actions.FUNCTIONS.select_point("select", (command.x,command.y))
        return actions.FUNCTIONS.no_op()

    def train_scv(self, obs):
        if (actions.FUNCTIONS.Train_SCV_quick.id in
                    obs.observation.available_actions):
            return actions.FUNCTIONS.Train_SCV_quick('now')
        return actions.FUNCTIONS.no_op()

    def select_scv(self, obs):
        scvs = self.get_units_by_type(obs, units.Terran.SCV)
        if len(scvs) > 0:
            scv = random.choice(scvs)
            return actions.FUNCTIONS.select_point("select", (scv.x,scv.y))
        return actions.FUNCTIONS.no_op()

    def move_scv(self, obs, position):
        if self.unit_type_is_selected(obs, units.Terran.SCV):
            return actions.FUNCTIONS.Move_screen("now", position)
        return actions.FUNCTIONS.no_op()

    def build_baracks(self, obs, position):
        if self.unit_type_is_selected(obs, units.Terran.SCV):
            if (actions.FUNCTIONS.Build_Barracks_screen.id in
                    obs.observation.available_actions):
                return actions.FUNCTIONS.Build_Barracks_screen('now', position)
        return actions.FUNCTIONS.no_op()

    def select_barracks(self, obs):
        barracks = self.get_units_by_type(obs, units.Terran.Barracks)
        if len(barracks) > 0:
            barrack = random.choice(barracks)
            return actions.FUNCTIONS.select_point("select", (barrack.x, barrack.y))
        return actions.FUNCTIONS.no_op()

    def build_supply(self, obs, position):
        if self.unit_type_is_selected(obs, units.Terran.SCV):
            if (actions.FUNCTIONS.Build_SupplyDepot_screen.id in
                    obs.observation.available_actions):
                return actions.FUNCTIONS.Build_SupplyDepot_screen('now', position)
        return actions.FUNCTIONS.no_op()

    def train_marine(self, obs):
        if self.unit_type_is_selected(obs, units.Terran.Barracks):
             if (actions.FUNCTIONS.Train_Marine_quick.id in
                    obs.observation.available_actions):
                return actions.FUNCTIONS.Train_Marine_quick('now')
        return actions.FUNCTIONS.no_op()

    def select_all_marines(self, obs):
        marines = self.get_units_by_type(obs, units.Terran.Marine)
        if len(marines) > 0:
            marine = random.choice(marines)
            return actions.FUNCTIONS.select_point('select_all_type', (marine.x, marine.y))
        return actions.FUNCTIONS.no_op()

    def move_marines(self, obs, position):
        if self.unit_type_is_selected(obs, units.Terran.Marine):
            return actions.FUNCTIONS.Move_screen("now", position)
        return actions.FUNCTIONS.no_op()
    
    def no_op(self):
        return actions.FUNCTIONS.no_op()

    def get_units_by_type(self, obs, unit_type):
        return [unit for unit in obs.observation.feature_units
                if unit.unit_type == unit_type]

    def unit_type_is_selected(self, obs, unit_type):
        if (len(obs.observation.single_select) > 0 and
            obs.observation.single_select[0].unit_type == unit_type):
            return True

        if (len(obs.observation.multi_select) > 0 and
            obs.observation.multi_select[0].unit_type == unit_type):
            return True
        return False
    
