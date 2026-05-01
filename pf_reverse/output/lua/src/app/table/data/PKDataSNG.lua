
local P = class("PKData", require("app.table.data.PKData"))

function P:assignRoomInfo(params)
	P.super.assignRoomInfo(self, params)

	self.room_info = params.sngroom_info
	self.blind_up_st = os.time()
end

function P:setPlaying(state)
	P.super.setPlaying(self, state)
	if state then
		local blind = self.room_info.blind_list[self.room_info.blind_level]
		if blind and blind.small_blind ~= self:getSmallBlind() then
			self:setSmallBlind(blind.small_blind)
			self:setAnte(blind.ante)

			bee.emit("evt_refreshBlind")
		end
	end
end

function P:getBustThreshold()
	return self.room_info.bust_threshold
end

function P:isSngStart()
	return self.room_info.is_sng_start
end

function P:getBlindLevel()
	return self.room_info.blind_level
end

function P:getBlindList()
	return self.room_info.blind_list
end

function P:getBlindUpTime()
	if not self.room_info.is_sng_start then
		return self.room_info.blind_list[1].duration
	end
	local blind = self.room_info.blind_list[self.room_info.blind_level]
	if blind and blind.small_blind ~= self:getSmallBlind() then
		return 0
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

function P:setBlindStatus(msg)
	self.room_info.upblind_time = msg.upblind_time
	self.room_info.is_sng_start = true
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

return P