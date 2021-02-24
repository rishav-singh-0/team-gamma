#!/usr/bin/env python

import rospy
import math
from sensor_msgs.msg import NavSatFix, LaserScan, Imu
from std_msgs.msg import String,Float32
import std_msgs.msg
import tf
from vitarana_drone.srv import *


class PathPlanner():

    def __init__(self):
        rospy.init_node('path_planner_beta')

        # Destination to be reached
        # [latitude, longitude, altitude]
        self.destination = [0, 0, 0]
        # Converting latitude and longitude in meters for calculation
        self.destination_xy = [0, 0]
        
        #*******************************************opt********************************#
        self.sudo_destination_reach=False#checking if its reached at the destination which is for delevery in csv file
        self.desired_destination=[0,0,0]#giving it to the threshould box if it has found marker
        #above 2 will being erased:::::)
        self.img_data=[0,0]#data which will come from the maeker_detect.py script
        self.pause_process=False#it will helpful to stop taking the data form the marker_detect and focus on destination reach
        self.reach_flag=False#for reaching at every position which is require threshould box
        self.pick=True#for deciding wather to pick or drop a box
        self.status="DELIVERY"#it will be either "delevery" or "returns"
        self.pick_drop_box=False
        self.msg_from_marker_find=False
        self.cnt=0
        self.attech_situation = False
        # self.destination_list=[[18.9999864489,71.9999430161,8.44099749139],
        #                        [(18.9999864489+4*0.000013552),(71.9999430161+0.000014245),8.44099749139],
        #                        [(18.9999864489+0.000013552),(71.9999430161+0.000014245),8.44099749139],
        #                        [(18.9999864489+0.000013552),71.9999430161,8.44099749139]]

        self.dst=[0,0,0]
        self.container=[0,0,0]
        self.kaam_aabhi_baki_hai=False
        self.altitude_interrup=True
        self.altitude=0
        self.limiter=[0,0,0]#for limiting the altitude due to current_location
        self.buffer_altitude=0
        self.drone_orientation_quaternion=[0,0,0,0]
        self.drone_orientation_euler=[0,0,0,0]
        self.pause_coordinates=[0,0]
        self.lock=True
        self.lock2=False

        #*******************************************opt********************************#
        
        # Present Location of the DroneNote
        self.current_location = [0, 0, 0]
        # Converting latitude and longitude in meters for calculation
        self.current_location_xy = [0, 0]

        # The checkpoint node to be reached for reaching final destination
        self.checkpoint = NavSatFix()
        self.desti_data=NavSatFix()

        # Initializing to store data from Lazer Sensors
        self.obs_range_top = [0,0,0,0]
        self.obs_range_bottom = []

        # Defining variables which are needed for calculation
        # diffrence of current and final position
        self.diff_xy = [0, 0]
        self.distance_xy = 0                # distance between current and final position

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
        self.grip_flag=rospy.Publisher('/gripp_flag',String,queue_size=1)
        self.destination_data=rospy.Publisher('/destination_data' , NavSatFix,queue_size=1)

        self.next_flag=rospy.Publisher('/next_destination_flag',Float32,queue_size=1)
        # Subscriber
        rospy.Subscriber('/final_setpoint', NavSatFix, self.final_setpoint_callback)
        rospy.Subscriber('/edrone/gps', NavSatFix, self.gps_callback)
        rospy.Subscriber('/edrone/range_finder_top', LaserScan, self.range_finder_top_callback)
        rospy.Subscriber('/edrone/gripper_check', String, self.gripper_check_callback)
        rospy.Subscriber('/marker_error', NavSatFix, self.marker_error_callback)
        rospy.Subscriber('/edrone/imu/data', Imu, self.imu_callback)
        

        rospy.Subscriber('/box_checkpoint',NavSatFix,self.csv_checkpoint)
        rospy.Subscriber('/edrone/range_finder_bottom', LaserScan, self.range_finder_bottom_callback)

    def gripper_client(self, check_condition):
        '''this function will call and wait for the gripper service'''

        rospy.wait_for_service('/edrone/activate_gripper')
        carry = rospy.ServiceProxy('/edrone/activate_gripper', Gripper)
        msg_container = carry(check_condition)
        return msg_container.result     # true if box is atteched and visa versa

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
        # print("holA")
        # print(msg.header.frame_id)


    def gripper_check_callback(self, state):
        self.attech_situation = state.data


    def final_setpoint_callback(self, msg):
        self.destination = [msg.latitude, msg.longitude, msg.altitude]

    def gps_callback(self, msg):
        # print(self.current_location[0]-msg.latitude)
        self.current_location = [msg.latitude, msg.longitude, msg.altitude]

    def range_finder_top_callback(self, msg):
        # print(self.drone_orientation_euler[0]*180/3.14)
        # print("hellloooooo")
        # print(self.drone_orientation_euler[1]*180/3.14)
        if(-2.5<=(self.drone_orientation_euler[0]*180/3.14)<=2.5 and -2.5<=(self.drone_orientation_euler[1]*180/3.14)<=2.5):
            if(msg.ranges[0]>0.4 and msg.ranges[1]>0.4 and msg.ranges[2]>0.4 and msg.ranges[3]>0.4):
                self.obs_range_top = msg.ranges
                # print(self.obs_range_top)

    def range_finder_bottom_callback(self, msg):
        if(msg.ranges[0]>0.410000 or (self.destination[2]-self.current_location[2])<0.1):
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


    def altitude_control(self):
        dist_z = self.current_location[2] - self.destination[2] + 3
        slope = dist_z / (self.distance_xy - 3)
        self.checkpoint.altitude = self.current_location[2] + (slope * dist_z)

    def threshould_box(self, limit):
        #print(self.pick_drop_box)
        # print(self.pause_process)
        # print(self.destination)
        # print("yoo",self.current_location)
       
        if -0.2 <= self.lat_to_x_diff(self.current_location[0]-self.destination[0])<= 0.2:
           
            if -0.2<= self.long_to_y_diff(self.current_location[1]-self.destination[1])<= 0.2:
                self.pick_drop_box=True
               
                if(self.pause_process):
                    self.msg_from_marker_find=True
                    print("self.lock2",self.lock)
                if (((-0.02<=(self.destination[2]-self.current_location[2]) <= 0.05) or (len(self.obs_range_bottom) and (self.obs_range_bottom[0]<=0.3840))) and self.pick ):
                    if(self.attech_situation):
                        self.reach_flag=True
                        self.pause_process=False
                        self.grip_flag.publish('True')
                        # self.next_flag.publish(1.0)
                        while( self.gripper_client(True)==False):
                            
                            self.gripper_client(True)
                        self.pick=False
                        self.pick_drop_box=False
                        self.next_flag.publish(1.0)
                        while(self.destination==self.dst):
                            continue
                        self.destination=self.dst
                        # self.lock=True
                
                elif((-2<(self.destination[2]-self.current_location[2]) < 2)and(self.obs_range_bottom[0]<=0.5100) and (not self.pick)):
                    if(self.attech_situation):
                            self.reach_flag=True
                            self.pause_process=False
                            self.grip_flag.publish('False')
                            # self.next_flag.publish(1.0)
                            self.pick=True
                            self.pick_drop_box=False
                            self.next_flag.publish(1.0)
                            while(self.destination==self.dst):
                                continue
                            self.destination=self.dst
                            # self.lock2=True
                            # if(self.status=="RETURN "):
                            #     self.status=="DELIVERY"
                       
                    
    def altitude_select(self):
        # print(self.checkpoint.altitude)
        # if(self.pick):
        #     self.altitude=self.destination[2]+2
        # else:
        if(self.limiter[2]==0):
            if((-0.08<self.current_location[2]-self.destination[2]<0.08) and self.altitude_interrup):
                print("current is big")
                self.altitude=16.75+3#self.destination[2]+1.5
            elif(not (-0.08<self.current_location[2]-self.destination[2]<0.08) and self.current_location[2]>self.destination[2] and self.altitude_interrup):
                if(self.limiter[0]==0):
                    print("hiiii")
                    self.buffer_altitude=self.current_location[2]+3
                    self.limiter[0]+=1
                self.altitude=self.buffer_altitude
            elif(self.current_location[2]<self.destination[2] and self.altitude_interrup):
                print("current is small")
                self.altitude=10.1#self.destination[2]+1
                # if(self.obs_range_bottom[0]<1):
                #     print("obs_bottom")
                #     self.altitude=self.current_location[2]+0.5
            self.limiter[2]+=1

        a=min(self.obs_range_top)
        # print(self.distance_xy)
        # print(a)

        # print()
        # print(self.distance_xy>a)
        # print(self.altitude_interrup)
        # print((self.obs_range_top[0]<=13 or self.obs_range_top[1]<=13 or self.obs_range_top[2]<=13 or self.obs_range_top[3]<=13))
        if(self.distance_xy>a and self.altitude_interrup and (self.obs_range_top[0]<=13 or self.obs_range_top[1]<=13 or self.obs_range_top[2]<=13 or self.obs_range_top[3]<=13)):
            
            print("yoo")
            self.altitude=self.current_location[2]+4.67

            # self.pause_coordinates=[self.current_location[0],self.current_location[1]]
            self.altitude_interrup=False
        # print(self.checkpoint.altitude)
        self.checkpoint.altitude=self.altitude
        # if(self.pause_coordinates[0]!=0):
        #     self.checkpoint.latitude=self.pause_coordinates[0]
        #     self.checkpoint.longitude=self.pause_coordinates[1]

    def check_altitude(self):
        
        # print(self.distance_xy)
        if( not self.altitude_interrup):
            if(-0.1<=self.altitude-self.current_location[2]<=0.1):
                print("achived")
            else:
                self.movement_in_1D=-6
                print("kaam aabhi baki hai")

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
        # self.movement_in_1D=[0,0]
        # self.destination=self.destination_list[self.cnt]
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

        # calculating maximum distance to be covered at once
        # it can be done more efficiently using another pid
        # for obs_distance in data:
        #     if 16 <= obs_distance:
        #         self.movement_in_1D = 2
        #     elif 9 <= obs_distance:
        #         self.movement_in_1D = 1
        #     elif(self.distance_xy<5):
        #         self.movement_in_1D=self.distance_xy
        #     else:
        # self.movement_in_1D[0] = 6
        # self.movement_in_1D[1] = 6
        for i in [0, 1]:
            d = data[self.direction_xy[i]]
            if d > 22:
                d = 22
            self.movement_in_1D = d * 0.65

        if(self.distance_xy<=8.0):
            self.movement_in_1D = self.distance_xy

        self.movement_in_plane = self.calculate_movement_in_plane(self.movement_in_1D)

        # print(self.movement_in_plane,self.movement_in_1D)

        # setting the values to publish
        
        self.checkpoint.latitude = self.current_location[0] - self.x_to_lat_diff(self.movement_in_plane[0])
        self.checkpoint.longitude = self.current_location[1] - self.y_to_long_diff(self.movement_in_plane[1])
        # self.altitude_select()
        # self.check_altitude()

        self.checkpoint.altitude = 25
        self.desti_data.latitude=self.destination[0]
        self.desti_data.longitude=self.destination[1]
        self.desti_data.altitude=self.destination[2]

        # Publishing
        self.pub_checkpoint.publish(self.checkpoint)
        
        self.destination_data.publish(self.desti_data)

    def marker_find(self):
        if(self.img_data==[0,0] and (not self.pause_process)):
            self.checkpoint.altitude=self.current_location[2]+1
            self.pub_checkpoint.publish(self.checkpoint)
        elif(self.img_data!=[0,0] and (not self.pause_process)):
            # print("yoooooooo")
            self.destination[0]=self.current_location[0]+self.x_to_lat_diff(self.img_data[0])
            self.destination[1]=self.current_location[1]+self.y_to_long_diff(self.img_data[1])
            self.checkpoint.latitude=self.destination[0]
            self.checkpoint.longitude=self.destination[1]

            self.pause_process=True
            # self.pub_checkpoint.publish(self.checkpoint)

    def pick_n_drop(self):
        
        self.checkpoint.altitude=self.destination[2]-0.3
        # self.pub_checkpoint.publish(self.checkpoint)
        # if(self.reach_flag):
        #     #print("yoo")
        #     if(self.pick and self.attech_situation):
        #         self.grip_flag.publish('True')
        #         # self.next_flag.publish(1.0)
        #         self.pick=False
                
        #     else:
        #         self.grip_flag.publish('False')
        #         # self.next_flag.publish(1.0)
        #         self.pick=True

        #     self.reach_flag=False#not self.reach_flag
        #     self.pick_drop_box=False
        #     # self.next_flag.publish(1.0)
        # #print(self.pick)
            
    def function_call(self):
        print(self.status)
        # print("msg_marker",self.msg_from_marker_find)
        # print("pause_process",self.pause_process)
        
        if(self.dst==[0,0,0]):
            return
        # print(self.msg_from_marker_find)
        if(not self.pause_process):
            self.destination=self.dst
        if(self.status=="DELIVERY"):
            if(not self.pick_drop_box):
                print("obstacle avoid")
                self.msg_from_marker_find=False
                self.pause_process=False
                self.lock=False
                self.lock2=False
                self.obstacle_avoid()
                # self.threshould_box()
            elif(self.pick_drop_box):
                if(not self.pick and not self.msg_from_marker_find):
                    print("marker_find")
                    self.limiter=[0,0,0]
                    self.altitude_interrup=True
                    self.marker_find()
                    # self.threshould_box()
                elif(self.pick or self.msg_from_marker_find):
                    # print("pick n drop")
                    self.limiter=[0,0,0]
                    self.pick_n_drop()
                    # self.threshould_box()
                    print("niche jao")
        elif(self.status=="RETURN "):
            if(not self.pick_drop_box):
                self.obstacle_avoid()
                # self.threshould_box()
                print("obstacle_avoid")
                #self.threshould_box()
            elif(self.pick_drop_box):
                self.pick_n_drop()
                # self.threshould_box()
                self.limiter=[0,0,0]
                self.altitude_interrup=True
                print("pick_n_drop")
        self.threshould_box(0.20)
        # print(self.checkpoint.altitude)
        self.pub_checkpoint.publish(self.checkpoint)

if __name__ == "__main__":
    planner = PathPlanner()
    rate = rospy.Rate(1/planner.sample_time)
    while not rospy.is_shutdown():
        planner.function_call()
        rate.sleep()