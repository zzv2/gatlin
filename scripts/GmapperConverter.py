#!/usr/bin/env python
import roslib
import sys
import rospy
import cv2
import time
import tf
from std_msgs.msg import String, Int8MultiArray, Float32MultiArray, Time, Header, Int32
from geometry_msgs.msg import Pose, Quaternion, Point, PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge, CvBridgeError
import numpy as np
from move_base_msgs.msg import MoveBaseActionGoal, MoveBaseActionFeedback, MoveBaseGoal
from actionlib_msgs.msg import GoalID, GoalStatusArray

#wiki.ros.org/gmapping
#wiki.ros.org/move_base

class GmapperConverter:

	def __init__(self):
		rospy.init_node('GmapperConverter', anonymous=True)
		print "initializing GmapperConverter"

		#self.image_sub = rospy.Subscriber("/camera/rgb/image_rect_color",Image,self.imagecallback, queue_size=1)
		#self.gmap_sub = rospy.Subscriber("/map", OccupancyGrid, self.mapcallback, queue_size=1)
		self.gmap_pub = rospy.Publisher("/gatlin/gmap_array", Int8MultiArray)
		#self.gmapinfo_pub = rospy.Publisher("/gatlin/gmap_info", Float32MultiArray)
		#self.time_pub = rospy.Publisher( "/gatlin/time", Time)

		#sets up subscriber of unity brain move to and cancel

		self.transform_listener = tf.TransformListener()
		self.map_pub = rospy.Publisher("/map_pose" , Pose)

		self.robot_pose_sub = rospy.Subscriber("/robot_pose_ekf/odom_combined_throttled", PoseWithCovarianceStamped, self.robotposecallback, queue_size = 1)
		self.robot_pose_pub = rospy.Publisher("/robot_pose", Pose)

		
		self.goal_pose_stamped_pub = rospy.Publisher("/goal_pose_stamped", PoseStamped)		
		self.move_to_goal_sub = rospy.Subscriber("/move_to_goal", Pose, self.goalcallback, queue_size = 1)
		self.move_to_goal_pub = rospy.Publisher("/move_base/goal", MoveBaseActionGoal)
		self.move_to_goal_count = 0

		self.cancel_goal_sub = rospy.Subscriber("/gatlin_cmd", Int32, self.cancelcallback, queue_size=1)
		self.cancel_move_pub = rospy.Publisher("/move_base/cancel", GoalID) #(actionlib_msgs/GoalID)
		self.LastStamp = None


		#move_base/feedback (move_base_msgs/MoveBaseActionFeedback)

		self.status_sub = rospy.Subscriber("/move_base/status", GoalStatusArray, self.statuscallback, queue_size = 1)

		self.lastnppose = np.array([-10000.0, -100000, -10000])


		

		rospy.spin()
		
	
	def robotposecallback(self, data) :
		#print "print odom data"
		#print data.pose.pose

		self.robot_pose_pub.publish(data.pose.pose)



	#receives a pose and publishes a goal for gmapper to walk t0
	def goalcallback(self, data):

		#TODO check status of route, if on another route, cancel it first
		#print "Creating goal Message"

		self.cancelcallback

		self.move_to_goal_count += 1

		g = MoveBaseActionGoal();

		sendtime = rospy.get_rostime()
		g.header = Header(self.move_to_goal_count, sendtime, "/map")

		g.goal_id = GoalID()
		
		g.goal_id.stamp = sendtime
		g.goal_id.id = "movement_num:"+str(self.move_to_goal_count)
		#print "asdfasdf"
		g.goal = MoveBaseGoal()
		g.goal.target_pose = PoseStamped()
		g.goal.target_pose.header = g.header #Header(self.move_to_goal_count, sendtime, "0")
		g.goal.target_pose.pose = data

		#print "Sending pose stamped of goal for rviz"
		psta = PoseStamped()
		psta.header = g.header
		psta.pose = data
		newnppose = np.array([data.position.x, data.position.y, data.position.z])
		if np.linalg.norm(newnppose -self.lastnppose) >.05 :
			self.goal_pose_stamped_pub.publish(psta)
			#print "Sending goal Message"
			self.move_to_goal_pub.publish(g)

		self.lastnp_pose = newnppose
		


	def cancelcallback(self, msg) :
		print "command in"
		if msg.data == 9:
			print "Cancel callback came in"
			self.cancelMovement()

	def cancelMovement(self) :
		print "Cancelling current action"
		if self.LastGoalID != None:
			self.cancel_move_pub.publish(self.LastGoalID);
	
	def statuscallback(self, data) :
		#received status callback
		l = len(data.status_list)
		#last is data.status_list[l-1].goal_id
		for i in xrange(0, l) :
			#print data.status_list[i].status
			if data.status_list[i].status == 1 :#this is the active one
				#print "Active GOAL:"
				#print data.status_list[i].goal_id
				self.LastGoalID = data.status_list[i].goal_id
				return
		self.LastGoalID = None

def main(args):
	print "initialized node Gmapper Converter"
	ic = GmapperConverter()

if __name__ == '__main__':
    main(sys.argv)
