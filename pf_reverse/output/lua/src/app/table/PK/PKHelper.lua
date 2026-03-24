local M = require("app.global.GFunctions")
local P = {}
-- PokerHelper = P

P.TYPE_2_NAME = {
	[10] = {desc="高牌", label="LAB_HIGH_CARD", type = 1},
	[20] = {desc="一对", label="LAB_ONE_PAIR", type = 2},
	[30] = {desc="两对", label="LAB_TWO_PAIRS", type = 3},
	[40] = {desc="三条", label="LAB_THREE_KIND", type = 4},
	[50] = {desc="顺子", label="LAB_STRAIGHT", type = 5},
	[60] = {desc="同花", label="LAB_FLUSH", type = 6},
	[70] = {desc="葫芦", label="LAB_FULL_HOUSE", type = 7},
	[75] = {desc="同花", label="LAB_FLUSH", type = 6},
	[80] = {desc="四条", label="LAB_QUADS", type = 8},
	[90] = {desc="同花顺", label="LAB_STRAIGHT_FLUSH", type = 9},
	[100] ={desc="皇家同花顺", label="LAB_ROYAL_FLUSH", type = 10},
}

-- 对成牌进行排序 按牌面点数相同张数多的靠前，再按数量相同牌面点数大的靠前显示
function P.getSortCards(cards)
	local ret = {}
	for k, v in ipairs(cards) do
		v.count = 1
		table.insert(ret, v)
	end
	for k, v in ipairs(cards) do
		for i = k + 1, #cards do
			if v.number == cards[i].number then
				v.count = v.count + 1
				cards[i].count = cards[i].count + 1
			end
		end
	end
	table.sort(ret, function(a, b)
		if a.count ~= b.count then
			return a.count > b.count
		end
		if a.number ~= b.number then
			return a.number > b.number
		end
		return a.color > b.color
	end)
	if ret[1].number == 14 and ret[2].number == 5 and ret[3].number == 4 and ret[4].number == 3 and ret[5].number == 2 then
		local tmp = ret[1]
		for i = 1, #ret - 1 do
			ret[i] = ret[i + 1]
		end
		ret[#ret] = tmp
	end
	return ret
end

function P.getCardType(handCards, publicCards, roomType)
	if GF.isOmahaRoom(roomType) then
		return P.getOmahaType(handCards, publicCards)
	end
	return P.getHoldemType(handCards, publicCards)
end

-- 获取 Omaha版型组合及名称
function P.getOmahaType(handCards, publicCards)
	if not handCards or #handCards == 0 then return nil, "" end
	local handList = {}
	for i = 1, #handCards - 1 do
		for j = i + 1, #handCards do
			table.insert(handList, {{number = GF.getCardNumber(handCards[i]), color = GF.getCardSuit(handCards[i])}, {number = GF.getCardNumber(handCards[j]), color = GF.getCardSuit(handCards[j])}})
		end
	end
	if not publicCards or 0 == #publicCards then
		local maxNumber, hands = nil, nil
		for _, v in ipairs(handList) do
			local num = v[1].number + v[2].number
			if v[1].number == v[2].number then
				num = num * 1000
			end
			if not maxNumber or num > maxNumber then
				maxNumber, hands = num, v
			end
		end
		if hands[1].number == hands[2].number then
			return hands, P.TYPE_2_NAME[20].label, P.TYPE_2_NAME[20].type
		end
		return hands, P.TYPE_2_NAME[10].label, P.TYPE_2_NAME[10].type
	end
	local publicList = {}
	for i = 1, #publicCards - 2 do
		for j = i + 1, #publicCards - 1 do
			for k = j + 1, #publicCards do
				table.insert(publicList, {
					{number = GF.getCardNumber(publicCards[i]), color = GF.getCardSuit(publicCards[i])}, 
					{number = GF.getCardNumber(publicCards[j]), color = GF.getCardSuit(publicCards[j])},
					{number = GF.getCardNumber(publicCards[k]), color = GF.getCardSuit(publicCards[k])},
				})
			end
		end
	end
	local retHands, retVal = nil, 0
	for _, hands in ipairs(handList) do
		for _, publics in ipairs(publicList) do
			local top_comb, type_val = P.__get_holdem_top_type_combination(hands, publics, false)
			if top_comb then
				if type_val > retVal then
					retHands, retVal= top_comb, type_val
				elseif type_val == retVal then
					if retVal == 20 then	-- 一对时有可能出现小对的总点数大于大对
						local n1, n2 = P._get_pair_number(retHands), P._get_pair_number(top_comb)
						if n1 < n2 then
							retHands, retVal= top_comb, type_val
						elseif n1 == n2 and P._get_total_num(top_comb) > P._get_total_num(retHands) then
							retHands, retVal= top_comb, type_val
						end
					elseif retVal == 30 then 	-- 两对
						local n1, n11 = P._get_two_pair_number(retHands)
						local n2, n22 = P._get_two_pair_number(top_comb)
						if n1 > n11 then n1, n11 = n11, n1 end
						if n2 > n22 then n2, n22 = n22, n2 end
						if n11 < n22 or (n11 == n22 and n1 < n2) then
							retHands, retVal= top_comb, type_val
						elseif (n1 == n2 and n11 == n22) and P._get_total_num(top_comb) > P._get_total_num(retHands) then
							retHands, retVal= top_comb, type_val
						end
					elseif retVal == 40 then	-- 三条
						local n1, n2 = P._get_three_number(retHands), P._get_three_number(top_comb)
						if n1 < n2 then
							retHands, retVal= top_comb, type_val
						elseif n1 == n2 and P._get_total_num(top_comb) > P._get_total_num(retHands) then
							retHands, retVal= top_comb, type_val
						end
					elseif retVal == 70 then 	-- 葫芦
						local n1, n2 = P._get_three_number(retHands), P._get_three_number(top_comb)
						if n1 < n2 then
							retHands, retVal= top_comb, type_val
						elseif n1 == n2 and P._get_total_num(top_comb) > P._get_total_num(retHands) then
							retHands, retVal= top_comb, type_val
						end
					elseif retVal == 50 or retVal == 90 then	-- 顺子 同花顺
						if P._get_straight_num(top_comb) > P._get_straight_num(retHands) then
							retHands, retVal= top_comb, type_val
						end
					elseif P._get_total_num(top_comb) > P._get_total_num(retHands) then
						retHands, retVal= top_comb, type_val
					end
				end
			end
		end
	end
	return retHands, P.TYPE_2_NAME[retVal].label, P.TYPE_2_NAME[retVal].type
end

function P._get_pair_number(comb)
	for k, v in ipairs(comb) do
		for i = k + 1, #comb do
			if v.number == comb[i].number then
				return v.number
			end
		end
	end
	return -1
end

function P._get_two_pair_number(comb)
	local n1, n2 = -1, -1
	for k, v in ipairs(comb) do
		for i = k + 1, #comb do
			if v.number == comb[i].number then
				if n1 == -1 then
					n1 = v.number
				else
					n2 = v.number
					break
				end
			end
		end
	end
	return n1, n2
end

function P._get_three_number(comb)
	for k, v in ipairs(comb) do
		for i = k + 1, #comb do
			if v.number == comb[i].number then
				for j = i + 1, #comb do
					if v.number == comb[j].number then
						return v.number
					end
				end
			end
		end
	end
	return -1
end

function P._get_straight_num(comb)
	local num = P._get_total_num(comb)
	if num == 28 then
		num = 15
	end
	return num
end

function P._get_total_num(comb)
	local n = 0
	for _, v in ipairs(comb) do
		n = n + v.number
	end
	return n
end

-- 获取Poker牌型组合及牌型名称
function P.getHoldemType(handCards, publicCards)
	if nil == handCards then
		return nil, ""
	end
	local hands = {}
	for _, v in ipairs(handCards) do
		hands[#hands + 1] = {number = GF.getCardNumber(v), color = GF.getCardSuit(v)}
	end
	
	if nil == publicCards or 0 == #publicCards then
		if hands[1].number == hands[2].number then
			return hands, P.TYPE_2_NAME[20].label, P.TYPE_2_NAME[20].type
		end
		return hands, P.TYPE_2_NAME[10].label, P.TYPE_2_NAME[10].type
	end
	local publics = {}
	for _, v in ipairs(publicCards) do
		publics[#publics + 1] = {number = GF.getCardNumber(v), color = GF.getCardSuit(v)}
	end
	local top_comb, type_val = P.__get_holdem_top_type_combination(hands, publics, false)
	if nil == top_comb then
		return
	end
	local _str = P.TYPE_2_NAME[type_val].label
	return top_comb, _str, P.TYPE_2_NAME[type_val].type
end

-- ---------------------------------------------------------
-- 获取数组选取n项的所有组合
-- ---------------------------------------------------------
function P.__get_combination_list(array, n)
	local m = #array
	local all_comb = {}
	local key_s = {}
	local comb_total = 0
	local function _collect_()
		local it = {}
		for _, idx in ipairs(key_s) do
			table.insert(it, array[idx])
		end
		return it
	end
	local function _forLoop(start, addc)
		for i = start, (m - n + addc) do
			key_s[addc] = i
			if addc == n then
				comb_total = comb_total + 1
				local itm = _collect_()
				table.insert(all_comb, itm)
			else
				_forLoop(i+1, addc+1)
			end
		end
	end
	_forLoop(1, 1)
	return all_comb
end

--is_sixplus 表示6+德州
function P.__get_holdem_top_type_combination(h_hands, h_boards, is_sixplus)
	local holdem_cards = table.merge_list(h_hands, h_boards)
	local all_combination_ls = P.__get_combination_list(holdem_cards, 5)

	local top_comb, type_val = P.__get_top_type_combination(all_combination_ls, is_sixplus)
	return top_comb, type_val
end

function P.__get_top_type_combination(all_comb_ls, is_sixplus)
	is_sixplus = is_sixplus or false

	local max_val = -1
	local same_type_combs = {}
	for i=1, #all_comb_ls do
		local comb = all_comb_ls[i]
		local pk_tp = P.__getFiveCardsType(comb, is_sixplus)
		if pk_tp >= 0 then
			local cur_val = P.POKER_TYPE[pk_tp].value
			if cur_val > max_val then
				max_val = cur_val
				same_type_combs = {}
				table.insert(same_type_combs, comb)
			elseif cur_val == max_val then
				table.insert(same_type_combs, comb)
			end
		end
	end
	-- print("same type combination count ", #same_type_combs, max_val)
	local _comb_ret
	if #same_type_combs == 1 then
		_comb_ret = same_type_combs[1]
		return _comb_ret, max_val
	end

	if max_val == 30 then -- 两对
		_comb_ret = P.__select_top_two_pairs(same_type_combs)
	elseif max_val == 50 or max_val == 90 or max_val == 100 then
		_comb_ret = P.__select_top_straight(same_type_combs, is_sixplus)
	else
		_comb_ret = P.__select_top_combination(same_type_combs)
	end
	return _comb_ret, max_val
end

-- ---------------------------------------------------------
-- 获取5张牌的牌型
-- ---------------------------------------------------------
P.POKER_TYPE = {
	[0] = {value=10}, -- "高牌",
	[1] = {value=20}, -- "一对",
	[2] = {value=30}, -- "两对",
	[3] = {value=40}, -- "三对",
	[4] = {value=70}, -- "葫芦",
	[7] = {value=50}, -- "顺子",
	[8] = {value=60}, -- "同花",
	[6] = {value=80}, -- "四条",
	[9] = {value=90}, -- "同花顺",
	[10] ={value=100}, -- "皇家同花顺",
	[11] ={value=75}, -- 6+德州的同花比葫芦大
}
function P.__getFiveCardsType(cardTb, is_sixplus)
	local pokerType = -1

	if cardTb and #cardTb == 5 then		
		table.sort(cardTb, function (a, b)
			return a.number < b.number
		end)

		local function isStraightType(cardTb)
			local isStraight = true
			local lastNumber = nil

			for i = 1, #cardTb do
				if not lastNumber then
					lastNumber = cardTb[i].number
				else
					local crtNumber = cardTb[i].number
					local gap = crtNumber - lastNumber

					if gap ~= 1 then
						isStraight = false

						break
					else
						lastNumber = crtNumber
					end
				end
			end

			if not isStraight then
				if cardTb[1].number == 2 and
					cardTb[2].number == 3 and cardTb[3].number == 4 and
					cardTb[4].number == 5 and cardTb[5].number == 14 then
					isStraight = true
				end

				if is_sixplus then
					--6+德州 A6789 是最小顺子
					if cardTb[1].number == 6 and
						cardTb[2].number == 7 and cardTb[3].number == 8 and
						cardTb[4].number == 9 and cardTb[5].number == 14 then
						isStraight = true
					end
				end
			end

			return isStraight
		end

		local function isFulshType(cardTb)
			local isSameColor = true
			local lastColor = nil
			for i = 1, #cardTb do
				if not lastColor then
					lastColor = cardTb[i].color
				else
					local crtColor = cardTb[i].color
					if lastColor ~= crtColor then
						isSameColor = false

						return isSameColor
					else
						lastColor = crtColor
					end
				end
			end

			return isSameColor
		end

		local function isRoyalFlushStraightType(cardTb)
			local isRoyalFlushStraight = false

			if cardTb[1].number == 10 and
				cardTb[2].number == 11 and cardTb[3].number == 12 and
				cardTb[4].number == 13 and cardTb[5].number == 14 then
				isRoyalFlushStraight = true
			end

			return isRoyalFlushStraight
		end

		local function getOtherType(cardTb)
			local pairCount = 0 
			for i = 1, #cardTb - 1 do
				for j = i+1, #cardTb do
					if cardTb[i].number == cardTb[j].number then
						pairCount = pairCount + 1
					end
				end
			end

			return pairCount
		end

		if isStraightType(cardTb) then
			if isFulshType(cardTb) then
				if isRoyalFlushStraightType(cardTb) then
					pokerType = 10
				else
					pokerType = 9
				end
			else
				pokerType = 7
			end

			return pokerType
		end

		if isFulshType(cardTb) then
			pokerType = 8
			if is_sixplus then
				pokerType = 11
			end
			return pokerType
		end

		pokerType = getOtherType(cardTb)
	end

	return pokerType
end

-- ---------------------------------------------------------
-- 获取两对牌型最大的组合
-- ---------------------------------------------------------
function P.__select_top_two_pairs(comb_ls)
	local high_pair_val = -1
	local pre_val = -1
	for i, comb in ipairs(comb_ls) do
		pre_val = -1
		for i = 1, 5 do
			if comb[i].number == pre_val then
				if pre_val > high_pair_val then
					high_pair_val = pre_val
				end
			else
				pre_val = comb[i].number
			end
		end
	end
	local high_pair_combs = {}
	for i, comb in ipairs(comb_ls) do
		local _cnt = 0
		for i = 1, 5 do
			if comb[i].number == high_pair_val then
				_cnt = _cnt + 1
			end
		end
		if _cnt == 2 then
			table.insert(high_pair_combs, comb)
		end
	end
	-- print("high_pair_val: ", high_pair_val)
	local high_pair_combs = P.__sort_combs(high_pair_combs)
	return high_pair_combs[1]
end

-- ---------------------------------------------------------
-- 获取顺子(同花顺)牌型最大的组合
-- ---------------------------------------------------------
function P.__select_top_straight(comb_ls, is_sixplus)
	comb_ls = P.__sort_combs(comb_ls)

	-- 处理最小顺子的情况
	local comb1 = comb_ls[1]

	if comb1 then
		if is_sixplus then
			if comb1[1].number == 6 and
				comb1[2].number == 7 and
				comb1[3].number == 8 and
				comb1[4].number == 9 and
				comb1[5].number == 14 then
				for i, comb in ipairs(comb_ls) do
					if comb[1].number == 6 and comb[5].number == 10 then
						return comb
					end
				end
			end

		else
			if comb1[1].number == 2 and
				comb1[2].number == 3 and
				comb1[3].number == 4 and
				comb1[4].number == 5 and
				comb1[5].number == 14 then
				for i, comb in ipairs(comb_ls) do
					if comb[1].number == 2 and comb[5].number == 6 then
						return comb
					end
				end
			end
		end
	end
	return comb_ls[1]
end

-- ---------------------------------------------------------
-- 对组合的数组进行排序, 获取最大组合 (每个组合已经内部排序)
-- ---------------------------------------------------------
function P.__sort_combs(comb_ls)
	local function compare_combination_item(a, b)
		for i=1, 5 do
			if a[i].number ~= b[i].number then
				if a[i].number > b[i].number then
					return true
				else
					return false
				end
			end
		end
		return false
	end
	local function _sort_func(a, b)
		return compare_combination_item(a, b)
	end
	table.sort(comb_ls, _sort_func )
	return comb_ls
end

-- ---------------------------------------------------------
-- 获取最大的组合
-- ---------------------------------------------------------
function P.__select_top_combination(comb_ls)
	comb_ls = P.__sort_combs(comb_ls)
	return comb_ls[1]
end

