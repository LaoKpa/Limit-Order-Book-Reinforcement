import argparse
import numpy as np
import copy

from limit_order_book import Limit_Order_book
from message_queue import Message_Queue
from order_queue import Order_Queue

n_state = 2
states_len = [2, 3]

parser = argparse.ArgumentParser(description='Dynamic Programming Algorithm')
parser.add_argument('--file_msg', default= '../datasets/GOOG_2012-06-21_34200000_57600000_message_10.csv', help='Message File Path')
parser.add_argument('--file_order', default= '../datasets/GOOG_2012-06-21_34200000_57600000_orderbook_10.csv', help= 'Order File Path')
parser.add_argument('--base_point', default=100, help='Base Point', type=int)
parser.add_argument('--order_direction', default=1, help='Buy 1, Sell -1', type=int)
parser.add_argument('--spread_cutoff', default=1.0, help='Cutoff for low bid-ask spread/high spread', type=float)
parser.add_argument('--start', default=34201, help='Start Time', type=float)
parser.add_argument('--end', default=34300, help='End Time', type=float)
args = parser.parse_args()
def Calculate_Q(V, H, T, I, L):
	"""
	Q is indexed by states and actions, where states include time_step T 
	(need to calculate 0 to T, T+1 is left with 0s), inventory I, and 
	limit order book states. Actions has dimension L
	V is the total number of shares, I is the number of inventory units.
	H is the total time left to sell all of the inventory. One period is H/T.
	"""
	Q = np.zeros((T + 2, I, states_len[0], states_len[1], L))
	Q_counter = np.zeros((T + 2, I, states_len[0], states_len[1], L))
	for t in np.arange(T, 0, -1):
		time = H*(t/T)
		next_time = time + H/T
		"""
		load_episodes will load the current orderbook at time H*(t/T)
		and the orderbook at next time step H*(t+1)/T
		"""
		episodes, real_times = load_episodes(time, next_time, H, V)
		for k in range(len(episodes)):
			episode= episodes[k] 
			real_time= real_times[k]
			episode_states = get_state(episode[0])
			prices = generate_prices(episode[0], L)
			for i in range(1, I):
				for a in range(L):
					a_price = prices[a]
					episode_next_state = get_state(episode[1])
					episode_next_i, im_reward = simulate(episode[0], (i+1)*int(V/I) , a_price, real_time[0], real_time[1])
					episode_next_i = int(episode_next_i/V*I)-1 # Have to change new order_size into inventory units.
					max_Q = np.amax(Q[t+1, episode_next_i, episode_next_state[0], episode_next_state[1], :])
					n = Q_counter[t, i, episode_states[0], episode_states[1], a]
					Q_counter[t, i, episode_states[0], episode_states[1], a] += 1
					Q[t, i, episode_states[0], episode_states[1], a] = n/(n+1) * Q[t, i, episode_states[0], episode_states[1], a] + 1/(n+1)*(im_reward+max_Q)
	return Q


def Optimal_strategy(Q):
	"""
	return argmax of each Q along the last axis (action)
	"""
	return np.argmax(Q, axis=len(Q.shape)-1)


def load_episodes(time, next_time, H, V):
	lob1_data, time_1 = read_order_book(time, H)
	lob1 = [Limit_Order_book(**lob_data, own_amount_to_trade=V,
					own_init_price=-args.order_direction*Limit_Order_book._DUMMY_VARIABLE,
					own_trade_type=args.order_direction) for lob_data in lob1_data]

	lob2_data, time_2 = read_order_book(next_time, H)
	lob2 = [Limit_Order_book(**lob_data, own_amount_to_trade=V,
					own_init_price=-args.order_direction*Limit_Order_book._DUMMY_VARIABLE,
					own_trade_type=args.order_direction) for lob_data in lob2_data]
	return list(zip(lob1, lob2)), list(zip(time_1, time_2))


def read_order_book(time, H):
	"""
	read the initial limit order book states from the file
	"""
	output= []
	time_output= []
	order= Order_Queue(args.file_order)
	real_time= args.start+time
	while real_time<args.end:
		mq= Message_Queue(args.file_msg)
		output.append(order.create_message_time(real_time, mq))
		time_output.append(real_time)
		real_time= real_time+H
	return output, time_output


def generate_prices(lob, L):
	"""
	generate a list of action prices based on current lob info
	"""
	current_mid_price = lob.bid[0] + (lob.ask[0] - lob.bid[0]) // 2
	return np.arange(current_mid_price-(L//2)*args.base_point, current_mid_price+(L-L//2)*args.base_point, args.base_point)

def get_state(lob):
	"""
	calculate states based on the limit order book
	State 1: bid-ask spread
	State 2: bid-ask volume misbalance
	"""
	spread = (lob.ask[0] - lob.bid[0])/100.0
	state1 = 0 if spread < args.spread_cutoff else 1
	state2 = np.sign(lob.ask_size[0] - lob.bid_size[0])
	return [state1, state2]

def simulate(lob, amount, a_price, time, next_time):
	"""
	simulate to next state, we need to calculate the remaining inventory given the current i and price a, and the immediate reward
	(revenue from the executed orders)
	"""
	mq = Message_Queue(args.file_msg)
	mq.pop_to_next_time(time)

	lob_copy = copy.deepcopy(lob)
	lob_copy.update_own_order(a_price,amount)
	mq_copy = copy.deepcopy(mq)

	for idx, message in mq_copy.pop_to_next_time(next_time):
		lob_copy.process(**message)
		if lob_copy.own_amount_to_trade == 0:
			break

	return [lob_copy.own_amount_to_trade, lob_copy.own_reward]

print (np.max(Calculate_Q(12, 10, 4, 2, 5)))
#V, H, T, I, L


