#!/usr/bin/env python

import rospy
import math
from sensor_msgs.msg import NavSatFix, LaserScan, Imu
from std_msgs.msg import String,Float32
import std_msgs.msg
import tf
# from vitarana_drone.srv import *

class PathPlanner():

    def __init__(self):
        rospy.init_node('path_planner_beta')

        # Destination to be reached
        # [latitude, longitude, altitude]
        self.destination = [0, 0, 0]
        # Converting latitude and longitude in meters for calculation
        self.destination_xy = [0, 0]
        
        #*******************************************opt********************************#
        # checking if its reached at the destination which is for delevery in csv file
        self.sudo_destination_reach = False
        # giving it to the threshould box if it has found marker
        self.desired_destination = [0, 0, 0]
        #above 2 will being erased:::::)
        # data which will come from the maeker_detect.py script
        self.img_data = [0, 0]
        # it will helpful to stop taking the data form the marker_detect and focus on destination reach
        self.pause_process = False
        self.reach_flag = False                     # for reaching at every position which is require threshould box
        self.pick = True                            # for deciding wather to pick or drop a box
        self.status = "DELIVERY"                    # it will be either "delevery" or "returns"
        self.pick_drop_box = False
        self.msg_from_marker_find = False
        self.cnt = 0
        self.attech_situation = False

        self.dst = [0, 0, 0]
        self.container = [0, 0, 0]
        self.kaam_aabhi_baki_hai = False
        self.altitude_interrup = True
        self.altitude = 0
        # for limiting the altitude due to current_location
        self.limiter = [0, 0, 0]
        self.buffer_altitude = 0
        self.drone_orientation_quaternion = [0, 0, 0, 0]
        self.drone_orientation_euler = [0, 0, 0, 0]
        self.pause_coordinates = [0, 0]
        self.stop_pick=True
        #*******************************************opt********************************#
        
        # Present Location of the DroneNote
        self.current_location = [0, 0, 0]
        # Converting latitude and longitude in meters for calculation
        self.current_location_xy = [0, 0]

        # The checkpoint node to be reached for reaching final destination
        self.checkpoint = NavSatFix()
        self.desti_data = NavSatFix()

        # Initializing to store data from Lazer Sensors
        self.obs_range_top = [0, 0, 0, 0]
        self.obs_range_bottom = []

        # Defining variables which are needed for calculation
        # diffrence of current and final position
        self.diff_xy = [0, 0]
        self.distance_xy = 0                # distance between current and final position
        self.diff_z = 0

        self.movement_in_1D = 0             # maximum movement to be done in one direction
        # [x, y] -> movement distribution in x and y
        self.movement_in_plane = [0, 0]
        # closest distance of obstacle (in meters)
        self.obs_closest_range = 8
        self.lock = False

        self.direction_xy = [0, 0]
        self.sample_time = 0.5

        # Publisher
        self.pub_checkpoint = rospy.Publisher('/checkpoint', NavSatFix, queue_size=1)
        self.grip_flag=rospy.Publisher('/gripp_flag', String, queue_size=1)
        self.destination_data=rospy.Publisher('/destination_data' , NavSatFix, queue_size=1)

        self.next_flag=rospy.Publisher('/next_destination_flag', Float32, queue_size=1)
        # Subscriber
        rospy.Subscriber('/final_setpoint', NavSatFix, self.final_setpoint_callback)
        rospy.Subscriber('/edrone/gps', NavSatFix, self.gps_callback)
        rospy.Subscriber('/edrone/range_finder_top', LaserScan, self.range_finder_top_callback)
        rospy.Subscriber('/edrone/gripper_check', String, self.gripper_check_callback)
        rospy.Subscriber('/marker_error', NavSatFix, self.marker_error_callback)
        rospy.Subscriber('/edrone/imu/data', Imu, self.imu_callback)
        
        rospy.Subscriber('/box_checkpoint', NavSatFix, self.csv_checkpoint)
        rospy.Subscriber('/edrone/range_finder_bottom', LaserScan, self.range_finder_bottom_callback)

    # def gripper_client(self, check_condition):
    #     '''this function will call and wait for the gripper service'''

    #     rospy.wait_for_service('/edrone/activate_gripper')
    #     carry = rospy.ServiceProxy('/edrone/activate_gripper', Gripper)
    #     msg_container = carry(check_condition)
    #     return msg_container.result     # true if box is atteched and visa versa

    def imu_callback(self, msg):
        self.drone_orientation_quaternion[0] = msg.orientation.x
        self.drone_orientation_quaternion[1] = msg.orientation.y
        self.drone_orientation_quaternion[2] = msg.orientation.z
        self.drone_orientation_quaternion[3] = msg.orientation.w
        (self.drone_orientation_euler[1], self.drone_orientation_euler[0], self.drone_orientation_euler[2]) = tf.transformations.euler_from_quaternion(
            [self.drone_orientation_quaternion[0], self.drone_orientation_quaternion[1], self.drone_orientation_quaternion[2], self.drone_orientation_quaternion[3]])

    def csv_checkpoint(self,msg):
        self.status=msg.header.frame_id
        self.container=[msg.latitude,msg.longitude,msg.altitude]
        if(self.dst!=self.container):
            self.dst=self.container
            # print(self.dst)

    def marker_error_callback(self, msg):
        self.img_data = [msg.latitude, msg.longitude]

    def gripper_check_callback(self, state):
        self.attech_situation = state.data

    def final_setpoint_callback(self, msg):
        self.destination = [msg.latitude, msg.longitude, msg.altitude]

    def gps_callback(self, msg):
        self.current_location = [msg.latitude, msg.longitude, msg.altitude]

    def range_finder_top_callback(self, msg):
        if(-2.5<=(self.drone_orientation_euler[0]*180/3.14)<=2.5 and -2.5<=(self.drone_orientation_euler[1]*180/3.14)<=2.5):
            if(msg.ranges[0]>0.4 and msg.ranges[1]>0.4 and msg.ranges[2]>0.4 and msg.ranges[3]>0.4):
                self.obs_range_top = msg.ranges
                # print(self.obs_range_top)

    def range_finder_bottom_callback(self, msg):
        if(msg.ranges[0]>0.41000 or abs(self.current_location[2]-self.destination[2])<0.1 ):
            self.obs_range_bottom = msg.ranges
            # print(self.obs_range_bottom[0])

    #mehods for distance measurement
    def lat_to_x_diff(self,ip_lat_diff):return (110692.0702932625*ip_lat_diff)
    def long_to_y_diff(self,ip_long_diff):return (-105292.0089353767*ip_long_diff)

    # Functions for data conversion between GPS and meter with respect to origin
    def lat_to_x(self, input_latitude): return 110692.0702932625 * (input_latitude - 19)
    def long_to_y(self, input_longitude): return - 105292.0089353767 * (input_longitude - 72)

    def x_to_lat_diff(self, input_x): return (input_x / 110692.0702932625)
    def y_to_long_diff(self, input_y): return (input_y / -105292.0089353767)

    def threshould_box(self):
        if(not self.pick):
            if -0.000009517 <= (self.destination[0]-self.current_location[0]) <= 0.000009517:
           
                if -0.0000093487 <= (self.destination[1]-self.current_location[1])<= 0.0000093487:
                    self.pick_drop_box=True
                
                    if(self.pause_process):
                        self.msg_from_marker_find=True
                    if(not self.pick and (len(self.obs_range_bottom) and (self.obs_range_bottom[0]<=0.500))):
                        if(self.attech_situation):
                            self.reach_flag=True
                            self.pause_process=False
                            if(self.status=="RETURN "):
                                self.pick_n_drop()
                                self.stop_pick=False
                            self.next_flag.publish(1.0)
                    elif ((-0.05<=(self.destination[2]-self.current_location[2]) <= 0.05) or (len(self.obs_range_bottom) and (self.obs_range_bottom[0]<=0.3800))):
                        if(self.attech_situation):
                            self.reach_flag=True
                            self.pause_process=False
                            if(self.status=="RETURN "):
                                self.pick_n_drop()
                                self.stop_pick=False
                            self.next_flag.publish(1.0)
        else:
            if -0.000004517 <= (self.destination[0]-self.current_location[0]) <= 0.000004517:
            
                if -0.0000013487 <= (self.destination[1]-self.current_location[1])<= 0.0000031487:
                    self.pick_drop_box=True
                
                    if(self.pause_process):
                        print("in the altitude control")
                        self.msg_from_marker_find=True
                    if(not self.pick and (len(self.obs_range_bottom) and (self.obs_range_bottom[0]<=0.500))):
                        if(self.attech_situation):
                            self.reach_flag=True
                            self.pause_process=False
                            if(self.status=="RETURN "):
                                self.pick_n_drop()
                                self.stop_pick=False
                            self.next_flag.publish(1.0)
                    elif ((-0.05<=(self.destination[2]-self.current_location[2]) <= 0.05) or (len(self.obs_range_bottom) and (self.obs_range_bottom[0]<=0.3800))):
                        if(self.attech_situation):
                            self.reach_flag=True
                            self.pause_process=False
                            
                            # if(self.status=="RETURN "):
                            self.pick_n_drop()
                            self.stop_pick=False
                            self.next_flag.publish(1.0)
                            self.pick_drop_box=False
                

    def altitude_select(self):
        # print(self.checkpoint.altitude)
        # if(self.pick):
        #     self.altitude=self.destination[2]+2
        # else:

        # self.checkpoint.altitude = self.destination[2] + 3 if self.diff_z > 0 else self.current_location[2] +3
        if(self.limiter[2]==0):
            if((-0.08<self.current_location[2]-self.destination[2]<0.08) and self.altitude_interrup):
                self.altitude=self.destination[2]+3
            else:
                if((self.current_location[2]>self.destination[2]) and self.altitude_interrup):
                    self.buffer_altitude=self.current_location[2]+3
                
                elif(self.current_location[2]<self.destination[2] and self.altitude_interrup):
                    self.buffer_altitude=self.destination[2]+2
                self.altitude=self.buffer_altitude
            self.limiter[2]+=1

        a=min(self.obs_range_top)
        if(self.distance_xy>a and self.altitude_interrup and (self.obs_range_top[0]<=13 or self.obs_range_top[1]<=13 or self.obs_range_top[2]<=13 or self.obs_range_top[3]<=13)):
            
            self.altitude=self.current_location[2]+4
            self.altitude_interrup=False

        self.checkpoint.altitude=self.altitude

    def check_altitude(self):
        
        # print(self.distance_xy)
        if( not self.altitude_interrup):
            if(-0.1<=self.altitude-self.current_location[2]<=0.1):
                print("achived")
            else:
                self.movement_in_1D=-6

    def calculate_movement_in_plane(self, total_movement):
        '''This Function will take the drone in straight line towards destination'''

        specific_movement = [0, 0]      # movement in specific direction that is x and y

        # Applying symmetric triangle method
        specific_movement[0] = (total_movement * self.diff_xy[0]) / self.distance_xy
        specific_movement[1] = (total_movement * self.diff_xy[1]) / self.distance_xy
        return specific_movement

    def obstacle_avoid(self):
        '''For Processing the obtained sensor data and publishing required
        checkpoint for avoiding obstacles'''
        if self.destination == [0, 0, 0]:
            return

        data = self.obs_range_top
        self.movement_in_plane = [0, 0]

        # destination in x and y form
        self.current_location_xy = [self.lat_to_x(self.destination[0]),
                                    self.long_to_y(self.destination[1])]

        self.destination_xy = [self.lat_to_x(self.current_location[0]),
                               self.long_to_y(self.current_location[1])]

        self.diff_xy = [self.destination_xy[0] - self.current_location_xy[0],
                        self.destination_xy[1] - self.current_location_xy[1]]

        self.distance_xy = math.hypot(self.diff_xy[0], self.diff_xy[1])

        self.diff_z = self.destination[2] - self.current_location[2]

        self.direction_xy[0] = 1 if self.diff_xy[0] < 0 else 3
        self.direction_xy[1] = 0 if self.diff_xy[1] < 0 else 2

        # print(self.direction_xy, self.diff_xy, data)

        # calculating maximum distance to be covered at once
        for i in [0, 1]:
            d = data[self.direction_xy[i]] if data[self.direction_xy[i]] < 24 else 24
            self.movement_in_1D = d * 0.65

        if(self.distance_xy <= 8.0):
            self.movement_in_1D = self.distance_xy

        # doge the obstacle if its closer than certain distance
        # for i in [0, 1]:
        #     if data[i] <= self.obs_closest_range:
        #         if i % 2 != 0:
        #             self.movement_in_plane[0] = data[i] - self.obs_closest_range
        #             self.movement_in_plane[1] = self.movement_in_1D
        #         else:
        #             self.movement_in_plane[0] = self.movement_in_1D
        #             self.movement_in_plane[1] = data[i] - self.obs_closest_range
        #     else:
        self.movement_in_plane = self.calculate_movement_in_plane(self.movement_in_1D)
        
        # altitude

        # setting the values to publish
        self.checkpoint.latitude = self.current_location[0] - self.x_to_lat_diff(self.movement_in_plane[0])
        self.checkpoint.longitude = self.current_location[1] - self.y_to_long_diff(self.movement_in_plane[1])
        # self.checkpoint.altitude = 24
        self.altitude_select()
        self.check_altitude()

        self.desti_data.latitude=self.destination[0]
        self.desti_data.longitude=self.destination[1]
        self.desti_data.altitude=self.destination[2]

        # Publishing
        # if(not self.pick_drop_box):
        self.pub_checkpoint.publish(self.checkpoint)
        
        self.destination_data.publish(self.desti_data)

    def marker_find(self):

        if(self.img_data==[0,0] and (not self.pause_process)):
            self.checkpoint.altitude=self.current_location[2]+1
            self.pub_checkpoint.publish(self.checkpoint)
        elif(self.img_data!=[0,0] and (not self.pause_process)):
            self.destination[0]=self.current_location[0]+self.x_to_lat_diff(self.img_data[0])
            self.destination[1]=self.current_location[1]+self.y_to_long_diff(self.img_data[1])
            self.checkpoint.latitude=self.destination[0]
            self.checkpoint.longitude=self.destination[1]

            self.pause_process=True
            # self.pub_checkpoint.publish(self.checkpoint)

    def pick_n_drop(self):
        
        self.checkpoint.altitude=self.destination[2]-0.3
        # self.pub_checkpoint.publish(self.checkpoint)
        if(self.reach_flag):
            if(self.pick and self.attech_situation):
                self.grip_flag.publish('True')
                # self.next_flag.publish(1.0)
                self.pick=False
                
            else:
                self.grip_flag.publish('False')
                # self.next_flag.publish(1.0)
                self.pick=True

            self.reach_flag=False#not self.reach_flag
            self.pick_drop_box=False
            # self.next_flag.publish(1.0)
            
    def function_call(self):
        print("hii")
        print("pause_process",self.pause_process)
        print("self.pick_drop_box",self.pick_drop_box)
        print("self.pick",self.pick)
        if(self.dst==[0,0,0]):
            return
        # print(self.msg_from_marker_find)
        if(not self.pause_process):
            self.destination=self.dst
        if(self.status=="DELIVERY"):
            if(not self.pick_drop_box):
                self.msg_from_marker_find=False
                self.pause_process=False
                self.obstacle_avoid()
                print("obs_avoid")
                
            elif(self.pick_drop_box):
                if(not self.pick and not self.msg_from_marker_find):
                    self.limiter=[0,0,0]
                    self.altitude_interrup=True
                    self.marker_find()
                    print("marker")
                    self.stop_pick=True
                elif(self.pick or self.msg_from_marker_find):
                    if(self.stop_pick):
                        self.pick_n_drop()
                    print("pick_drop")
                    # self.pick_n_drop()
        elif(self.status=="RETURN "):
            if(not self.pick_drop_box):
                self.obstacle_avoid()
                self.stop_pick=True
                # self.threshould_box()
                print("obstacle_avoid")
                #self.threshould_box()
            elif(self.pick_drop_box):
                if(self.stop_pick):
                    self.pick_n_drop()
                # self.threshould_box()
                self.limiter=[0,0,0]
                self.altitude_interrup=True
                print("pick_n_drop")
        self.threshould_box()
        # print(self.checkpoint.altitude)
        self.pub_checkpoint.publish(self.checkpoint)

if __name__ == "__main__":
    planner = PathPlanner()
    rate = rospy.Rate(1/planner.sample_time)
    while not rospy.is_shutdown():
        planner.function_call()
        rate.sleep()