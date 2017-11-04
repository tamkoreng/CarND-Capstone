#!/usr/bin/env python

import rospy
from geometry_msgs.msg import PoseStamped
from styx_msgs.msg import Lane, Waypoint
from std_msgs.msg import Int32
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import TwistStamped

import math
import tf
import numpy as np

'''
This node will publish waypoints from the car's current position to some `x` distance ahead.

As mentioned in the doc, you should ideally first implement a version which does not care
about traffic lights or obstacles.

Once you have created dbw_node, you will update this node to use the status of traffic lights too.

Please note that our simulator also provides the exact location of traffic lights and their
current status in `/vehicle/traffic_lights` message. You can use this message to build this node
as well as to verify your TL classifier.

TODO (for Yousuf and Aaron): Stopline location for each traffic light.
'''

LOOKAHEAD_WPS = 40 # Number of waypoints we will publish. You can change this number


class WaypointUpdater(object):
    def __init__(self):
        rospy.init_node('waypoint_updater')

        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)

        # TODO: Add a subscriber for /traffic_waypoint and /obstacle_waypoint below
        rospy.Subscriber('/traffic_waypoint', Int32, self.traffic_cb)
        rospy.Subscriber('/obstacle_waypoint', PointCloud2, self.obstacle_cb)
        rospy.Subscriber('/current_velocity', TwistStamped, self.velocity_cb)

        self.final_waypoints_pub = rospy.Publisher('final_waypoints', Lane, queue_size=1)

        # TODO: Add other member variables you need below
        self.pose_t = None # pose at current time t
        self.waypoints_base = None # base waypoints
        self.LenMapWP = 0 #map length
        self.tl_dis  = 300
        self.loop()
        self.v_t = 0 # current vehicle speed
        self.dis2future = np.zeros(LOOKAHEAD_WPS)
        self.RunFrq = None
        #self.decel_limit = rospy.get_param('~decel_limit', -5)
        #self.accel_limit = rospy.get_param('~accel_limit', 1.)
        # self.decel_limit = -3 #
        # self.accel_limit = 1
        self.InStopping = None
        #rospy.spin()

    def loop(self):
        self.RunFrq = 50 # Running frequency 50-Hz
        rate = rospy.Rate(self.RunFrq)
        self.InStopping = 0
        while not rospy.is_shutdown():
            if (self.pose_t is not None) and (self.waypoints_base is not None):
                self.get_final_waypoints()
                self.publish_final_waypoints()
                #pass
            rate.sleep()
        rospy.spin()

    def pose_cb(self, msg):
        # TODO: Implement
        self.pose_t = msg
        #pass

    def waypoints_cb(self, waypoints):
        # TODO: Implement
        pass
        self.waypoints_base = waypoints.waypoints
        # ypoints
        self.LenMapWP = len(self.waypoints_base)
        #rospy.logwarn('base_waypoints received - size:%s', self.waypoints_base)

    def velocity_cb(self, velocity):
        self.v_t = velocity.twist.linear.x
        #rospy.logwarn('current speed:%s', self.v_t)

    def traffic_cb(self, msg):
        # TODO: Callback for /traffic_waypoint message. Implement
        #self.tl_dis = msg.data
        #self.tl_dis = 1000
        pass

    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        pass

# ONLY FOR DEBUGGING: traffic light position simulator
    def update_tl_dis(self):
        self.tl_dis += -self.v_t/self.RunFrq
        if self.tl_dis<0: self.tl_dis=0
        if self.InStopping is 1 and self.tl_dis<3.0 and self.v_t< 0.00001:
            self.InStopping=0
            self.tl_dis = 300


    def get_waypoint_velocity(self, waypoint):
        return waypoint.twist.twist.linear.x

    def set_waypoint_velocity(self, waypoints, waypoint, velocity):
        waypoints[waypoint].twist.twist.linear.x = velocity

    def distance(self, waypoints, wp1, wp2):
        dist = 0
        dl = lambda a, b: math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2  + (a.z-b.z)**2)
        for i in range(wp1, wp2+1):
            dist += dl(waypoints[wp1].pose.pose.position, waypoints[i].pose.pose.position)
            wp1 = i
        return dist

# dis of current pose to future waypoints
    def distance_t2future(self):
        self.dis2future = np.zeros(LOOKAHEAD_WPS)
        self.dis2future[0] = self.distance2(self.final_waypoints[0].pose.pose.position, self.pose_t.pose.position)
        for i in range(1, LOOKAHEAD_WPS):
            self.dis2future[i]= self.dis2future[i-1]+ self.distance2(self.final_waypoints[i].pose.pose.position, self.final_waypoints[i-1].pose.pose.position)

    def distance2(self, a, b):
        #return lambda a, b: math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2)
        return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2)

    def find_closest(self, position):
        min_dis = 100000
        index_closest = 0
        for i in range(len(self.waypoints_base)):
            dist = self.distance2(position, self.waypoints_base[i].pose.pose.position)
            if dist < min_dis:
                min_dis = dist
                index_closest = i
        return index_closest


    def find_next(self, position, yaw_t):
        index_next= self.find_closest(position)
        map_x = self.waypoints_base[index_next].pose.pose.position.x
        map_y = self.waypoints_base[index_next].pose.pose.position.y
        heading = math.atan2(map_y - position.y, map_x - position.x)
        if math.fabs(yaw_t-heading)> math.pi/4:
            index_next += 1
        return index_next

    def get_yaw_t(self):
        orientation = [
            self.pose_t.pose.orientation.x,
            self.pose_t.pose.orientation.y,
            self.pose_t.pose.orientation.z,
            self.pose_t.pose.orientation.w]
        euler = tf.transformations.euler_from_quaternion(orientation)
        return euler[2]   # z direction

# Plan velocity
    def update_velocity(self):
        self.distance_t2future()
        dec_schedule = -1.0
        s = self.v_t**2/(2*np.absolute(dec_schedule ))
        # set brake mode when approaching traffic light
        if self.InStopping is 0 and (self.tl_dis-2) < s:
            self.InStopping=1

        # plan vehicle speed during cruise/acc
        if self.InStopping is 0:
            vel_RateLimit = 1.5 # acc
            for i in range(0, LOOKAHEAD_WPS):
                spd_target = np.sqrt(2*vel_RateLimit*self.dis2future[i] + (1.1*self.v_t)**2) #spd_target
                if spd_target>11: spd_target = 11
                #spd_target = 11
                self.final_waypoints[i].twist.twist.linear.x= spd_target #spd_target

        # plan speed during braking
        if self.InStopping is 1:
            dec_target = dec_schedule
            for i in range(0, LOOKAHEAD_WPS):
                ds = self.tl_dis -2- self.dis2future[i]
                if ds<0: ds=0
                self.final_waypoints[i].twist.twist.linear.x = np.sqrt(2*np.absolute(dec_target)*ds)


    def get_final_waypoints(self):
        yaw_t = self.get_yaw_t()
        index_nxtw = self.find_next(self.pose_t.pose.position, yaw_t)
        self.final_waypoints = self.waypoints_base[index_nxtw:index_nxtw+LOOKAHEAD_WPS]
        if index_nxtw+LOOKAHEAD_WPS > self.LenMapWP:
            self.final_waypoints[index_nxtw:self.LenMapWP] = self.waypoints_base[index_nxtw:self.LenMapWP]
            self.final_waypoints[self.LenMapWP+1:index_nxtw+LOOKAHEAD_WPS]=self.waypoints_base[1:index_nxtw+LOOKAHEAD_WPS-self.LenMapWP]
        else:
            self.final_waypoints = self.waypoints_base[index_nxtw:index_nxtw+LOOKAHEAD_WPS]

        self.update_velocity()
        self.update_tl_dis()

        # rospy.logwarn('traffic light distance:%s, spd actual:%s, InStopping:%s, spd target[0, 1, final]:%s, %s, %s',
        #                 self.tl_dis, self.v_t, self.InStopping,self.final_waypoints[0].twist.twist.linear.x,
        #                 self.final_waypoints[1].twist.twist.linear.x,self.final_waypoints[LOOKAHEAD_WPS-1].twist.twist.linear.x)

    def publish_final_waypoints(self):
        fw = Lane()
        fw.header.stamp = rospy.Time(0)
        fw.waypoints = self.final_waypoints
        self.final_waypoints_pub.publish(fw)


if __name__ == '__main__':
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')
