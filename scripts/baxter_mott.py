#!/usr/bin/env python
import time
from threading import Thread, Lock
import rospy, sys, tf
from math import *
from std_msgs.msg import *
from geometry_msgs.msg import *
from tf.transformations import *
from tf import *
from tf.msg import *
from copy import deepcopy
from gatlin.msg import *
from gatlin.srv import *
from config import *
from Dynamic import *
from random import randint

def distance(v1,v2):
	return np.linalg.norm(vector3_to_numpy(v1) - vector3_to_numpy(v2))

def length(v):
	return math.sqrt(np.dot(v, v))

def angle(v1, v2):
	return math.acos(np.dot(v1, v2) / (length(v1) * length(v2)))

class Nav_Manip_Controller :

	def grabObject(self, dynamic_pose) :
		#holding_object = False
		#while not holding_object :
		while True:
			if self.command_state == self.CANCELLED :
				return
			self.pauseCommand()

			self.publishResponse("Attempting to grab %s_%s" % (dynamic_pose.color, dynamic_pose.id))

			resp = self.move_arm("OPEN_GRIPPER", PoseStamped())

			def getOffsetPose():
				# rospy.logerr(dynamic_pose.ps)
				base_pose = self.transform_pose(self.BASE_FAME, dynamic_pose.ps)
				base_to_ar_t = transform_from_pose(base_pose.pose)

				offset_t = Transform()
				offset_t.translation = Vector3(-0.010, -0.000, -0.084)
				offset_t.rotation = Quaternion(-0.7071, -0.7071, 0.0000, 0.0000)
				# offset_inv_t = inverse_transform(offset_t)

				base_to_offset_t = multiply_transforms(base_to_ar_t, offset_t)
				base_pose_offset = deepcopy(base_pose)
				base_pose_offset.pose = transform_to_pose(base_to_offset_t)

				q = base_pose_offset.pose.orientation
				rpy = euler_from_quaternion([q.x,q.y,q.z,q.w])
				q = quaternion_from_euler(3.1415, 0.0, rpy[2])
				base_pose_offset.pose.orientation = Quaternion(q[0],q[1],q[2],q[3])
				return base_pose_offset

			# base_pose_offset = self.transform_pose(self.BASE_FAME, dynamic_pose.ps)
			base_pose_offset = getOffsetPose()


			base_pose_offset.pose.position.z += .10
			resp = self.move_arm("MOVE_TO_POSE_INTERMEDIATE", base_pose_offset)

			# base_pose_offset = self.transform_pose(self.BASE_FAME, dynamic_pose.ps)
			base_pose_offset = getOffsetPose()
			resp = self.move_arm("MOVE_TO_POSE_INTERMEDIATE", base_pose_offset)

			repeat = False
			if not resp.success:
				rospy.logerr("MOVE_TO_POSE_INTERMEDIATE FAILED")
				repeat = True
				# try moving to it again
				#self.servoBaseToDynamicPos(self.object_dp)
				#TODO check this
				rospy.sleep(.5)

			if not repeat: break

		self.pauseCommand()

		resp = self.move_arm("CLOSE_GRIPPER", PoseStamped())

		self.pauseCommand()

		#resp = self.move_arm("RESET_ARM", PoseStamped())
		# base_pose.pose.position.z += .1
		# resp = self.move_arm("MOVE_TO_POS", base_pose)
		# if not resp.success:
		# 	rospy.logerr("RESET_ARM FAILED")

		# no object detection in last second, it is likely in robot's hand
		#if time.time() - dynamic_pose.last_update > 1 :
		#holding_object = True

		self.publishResponse("Grabbed %s_%s" % (dynamic_pose.color, dynamic_pose.id))

	def pauseCommand(self) :
		while self.command_state == self.PAUSING :
			rospy.sleep(.03)

	def releaseObject(self, dynamic_pose) :
		if self.command_state == self.CANCELLED :
			return

		self.pauseCommand()

		self.publishResponse("Releasing object to %s_%s" % (dynamic_pose.color, dynamic_pose.id))
		base_pose = self.transform_pose(self.BASE_FAME, dynamic_pose.ps)
		resp = self.move_arm("MOVE_TO_POSE_INTERMEDIATE", base_pose)

		self.pauseCommand()

		if not resp.success:
				rospy.logerr("MOVE_TO_POSE_INTERMEDIATE FAILED")
		resp = self.move_arm("OPEN_GRIPPER", PoseStamped())

		self.pauseCommand()
		base_pose.pose.position.z += .1
		resp = self.move_arm("MOVE_TO_POSE", base_pose)

	def interActionDelay(self, delay) : #if user tells command to quit, then you don't want delays to stack
	 	if self.command_state == self.RUNNING :
			rospy.sleep(delay)

	def run_mott_sequence(self) :
		if self.object_dp.ps == None:
			rospy.logerr("object_pose not set")
			return

		self.grabObject(self.object_dp)
		
		self.interActionDelay(1)

		self.releaseObject(self.target_dp)

		self.interActionDelay(1)

		resp = self.move_arm("RESET_ARM", PoseStamped())

		if self.command_state == self.RUNNING :
			self.publishResponse("finished mott") #string must contain finished
		elif self.command_state == self.PAUSING :
			self.publishResponse("finished mott while pausing!?!?") 
		elif self.command_state == self.CANCELLED :
			self.publishResponse("quitting on user command") 

	def MottCallback(self, data) :
		# rospy.logerr(data)

		self.dm.dynamic_poses = []
		self.object_dp = self.dm.create_dp(self.FIXED_FRAME)
		self.target_dp = self.dm.create_dp(self.FIXED_FRAME)

		self.command_state = self.RUNNING

		if data.object_pose_topic != "" :
			self.object_dp.subscribe_name(data.object_pose_topic)

		if data.target_pose_topic != "" :
			self.target_dp.subscribe_name(data.target_pose_topic)
		
		if (data.object_pose) :
			self.object_dp.set_pose(data.object_pose)

		if (data.target_pose) :
			self.target_dp.set_pose(data.target_pose)
		
		rospy.sleep(.2)

		if data.command == "mott" :
			self.run_mott_sequence()
		else:
			rospy.logerr("Invalid Command: %s" % data.command)

	def MottCommandCallback(self, data) :
		rospy.loginfo("received "+data.data)
		data.data = data.data.lower()
		if "cancel" in data.data :
			rospy.loginfo("State = cancelling action")
			self.command_state = self.CANCELLED
		elif "paus" in data.data :
			rospy.loginfo("state = pausing")
			self.command_state = self.PAUSING
		elif "run" in data.data :
			rospy.loginfo("state = running")
			self.command_state = self.RUNNING

	def publishResponse(self, statement) :
		rospy.loginfo(statement)
		self.response_pub.publish(statement)

	# get the distance from the base to the given pose
	def distanceToPose(self, ps) :
		origin = Point(0,0,0)
		pose = self.transform_pose(self.BASE_FAME, ps)
		return distance(origin, pose.pose.position)

	# transform the pose stamped to the new frame
	def transform_pose(self, new_frame, ps):
		if ps.header.frame_id == new_frame:
			return ps
		try:
			temp_ps = deepcopy(ps)
			temp_ps.header.stamp = rospy.Time(0)
			self.tfl.waitForTransform(temp_ps.header.frame_id, new_frame, rospy.Time(0), rospy.Duration(4.0))
			new_pose = self.tfl.transformPose(new_frame, temp_ps)
			new_pose.header.stamp = deepcopy(pose.header.stamp)
			return new_pose
		except Exception as e:
			rospy.logerr(e)
			rospy.logerr("no transform")
			return None

	

	def __init__(self):
		rospy.init_node('baxter_nav_manip_controller')
		limb = rospy.get_param('~limb')
		self.limb = limb
		self.robot_name = "baxter_"+limb

		#self.robot_pose = DynamicPose()
		#self.robot_pose.subscribe("/robot_pose") #TODO change to end effector position??
		
		self.tfl = tf.TransformListener()

		# DynamicManager init
		self.dm = DynamicManager(self.tfl)
		self.dm.add_ol_sub("/server/ar_marker_list")

		self.RUNNING = 0
		self.PAUSING = 1
		self.CANCELLED = 2
		self.command_state = 0 #keeps track of running, pausing, cancelled

		#self.FIXED_FRAME = "global_map"
		self.FIXED_FRAME = "base"
		self.BASE_FAME = "base"#TODO look into

		robot = "baxter_" + limb
		self.response_pub = rospy.Publisher("/%s_mott_response" % robot, String, queue_size = 1)
		self.baxter_cmd_pub = rospy.Publisher("/%s_cmd" % robot, Int32, queue_size = 1)

		rospy.Subscriber("/%s_mott" % robot, Mott, self.MottCallback, queue_size = 1)
		rospy.Subscriber("/%s_mott_command" % robot, String, self.MottCommandCallback, queue_size = 1)

		# self.move_arm = createServiceProxy("baxter/move/arm", MoveRobot, self.robot_name)
		self.move_arm = createServiceProxy("/%s/move/arm" % robot, MoveRobot)

		rospy.spin()

if __name__ == "__main__":
	Nav_Manip_Controller()