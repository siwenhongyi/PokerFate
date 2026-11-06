
local P = class("PKDataMTT", require("app.table.data.PKData"))

function P:assignRoomInfo(params)
	P.super.assignRoomInfo(self, params)

	self:setRoomInfo(params)
end

function P:setRoomInfo(params)
	self.room_info = params.mttroom_info
	self.blind_up_st = os.time()
	self.break_left_time_st = os.time()

	self.addon_left_sec_st = os.time()
end

function P:setPlaying(state)
	P.super.setPlaying(self, state)
	if state then
		self:refreshBlindLevel()

		self.room_info.is_mtt_start = true
	end
end

function P:refreshBlindLevel()
	local blind = self.room_info.blind_list[self.room_info.blind_level]
	if blind and blind.small_blind ~= self:getSmallBlind() then
		self:setSmallBlind(blind.small_blind)
		self:setAnte(blind.ante)

		bee.emit("evt_refreshBlind")
	end
end

function P:getBustThreshold()
	return self.room_info.bust_threshold
end

function P:isMttStart()
	return self.room_info.is_mtt_start
end

function P:getRestLeftTime()
	if self.room_info.break_left_time > 0 then
		local dt = (self.room_info.break_left_time or 0) - (os.time() - (self.break_left_time_st or 0))
		if dt <= 0 then
			dt = 0
			self.room_info.break_left_time = 0
		end
		return dt
	end
	return 0
end

function P:getBlindList()
	return self.room_info.blind_list
end

function P:getBlindUpTime()
	if not self.room_info.is_mtt_start then
		return self.room_info.blind_list[1].duration
	end
	local blind = self.room_info.blind_list[self.room_info.blind_level]
	if blind and blind.small_blind ~= self:getSmallBlind() then
		return 0
	end
	if self:getRestLeftTime() > 0 then
		return self.room_info.upblind_time
	end
	if self.room_info.upblind_time and self.blind_up_st then
		local dt = self.room_info.upblind_time - (os.time() - self.blind_up_st)
		return dt > 0 and dt or 0
	end
	return 0
end

function P:getNextBlindInfo()
	for k, v in ipairs(self.room_info.blind_list) do
		if v.small_blind == self.room_info.sb then
			return self.room_info.blind_list[k + 1]
		end
	end
	return nil
end

function P:getBlindLevel()
	for k, v in ipairs(self.room_info.blind_list) do
		if v.small_blind == self.room_info.sb then
			return k
		end
	end
	return self.room_info.blind_level
end

function P:setBlindStatus(msg)
	self.room_info.upblind_time = msg.upblind_time
	self.room_info.is_mtt_start = true
	self.room_info.blind_level = msg.blind_level
	self.blind_up_st = os.time()

	if not self:isPlaying() then
		local blind = self.room_info.blind_list[self.room_info.blind_level]
		if blind and blind.small_blind ~= self:getSmallBlind() then
			self:setSmallBlind(blind.small_blind)
			self:setAnte(blind.ante)
		end
	end
end

function P:setAddOnBuyinRemainTime(dt)
	if dt and dt > 0 then
		self.room_status.addon_left_sec = dt
		self.addon_left_sec_st = os.time()
		self.room_status.is_addoning = true
	else
		self.room_status.addon_left_sec = 0
		self.addon_left_sec_st = nil
		self.room_status.is_addoning = false
	end
end

function P:getAddOnBuyinRemainTime()
	local dt = 0
	if self.room_status.is_addoning and self.addon_left_sec_st then
		dt = self.room_status.addon_left_sec - os.time() + self.addon_left_sec_st
	end
	return dt
end

return P