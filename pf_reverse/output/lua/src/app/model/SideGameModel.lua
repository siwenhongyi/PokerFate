local P = class("SideGameModel", BaseModel)

function P:ctor(logic)
	self.saveData = {cloud = {}}
	P.super.ctor(self)
end

function P:reqGetSideGameConfREQ()
	Net:sendReq("pb.GetSideGameConfREQ", {game_type = GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME})
end

function P:evt_refreshLevel()
	self:refreshNewDot()
end

function P:evt_ExpChangeRSP()
	self:refreshNewDot()
end

function P:refreshNewDot()
	if self:isPinballUnlock() then
		if self:isShowPinball() then
			RedManager:removeTag(RedTag.Pinball)
		else
			RedManager:addTag(RedTag.Pinball)
		end
	else
		RedManager:removeTag(RedTag.Pinball)
	end
end

function P:getLastSideGameType()
    return self.saveData["lastSideGame" .. PlayerModel:getUid()] or GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME
end

function P:setLastSideGameType(gameType)
    self.saveData["lastSideGame" .. PlayerModel:getUid()] = gameType
    self:onSave()
end

function P:evt_GetSideGameConfRSP(msg)
	if msg.game_type ~= GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME then
		return
	end
	
	local conf = json.decode(msg.conf)
	self._exportConf = {}
	for i, v in ipairs(conf.export) do
		self._exportConf[v.export_id] = v.rate
	end
	self._pinball_conf = conf.tpl_conf
	self._pinball_balls = conf.balls

	bee.emit("evt_setPinballConf")
end

function P:getExportConf()
	return self._exportConf
end

function P:getPinballConf()
	return self._pinball_conf
end

function P:getPinballBalls()
	return self._pinball_balls
end

function P:isShowPinball()
	return self.saveData["isShowPinball" .. PlayerModel:getUid()] == 1
end

function P:setShowPinball()
	self.saveData["isShowPinball" .. PlayerModel:getUid()] = 1
	RedManager:removeTag(RedTag.Pinball)
	self:onSave()
end

function P:isPinballUnlock()
    return tpl_system_info[101].level <= PlayerModel:getCurLevel()
end

function P:getPinballLastLv()
	return self.saveData["pinballLastLv" .. PlayerModel:getUid()]
end

function P:setPinballLastLv(lv)
	self.saveData["pinballLastLv" .. PlayerModel:getUid()] = lv
	self:onSave()
end

function P:getPinballLastChip()
	return self.saveData["pinballLastChip" .. PlayerModel:getUid()]
end

function P:setPinballLastChip(chip)
	self.saveData["pinballLastChip" .. PlayerModel:getUid()] = chip
	self:onSave()
end

function P:getPinballLastBallCount()
	return self.saveData["pinballLastBallCount" .. PlayerModel:getUid()]
end

function P:setPinballLastBallCount(ballCount)
	self.saveData["pinballLastBallCount" .. PlayerModel:getUid()] = ballCount
	self:onSave()
end

function P:getColorGameLastLv()
	return self.saveData["colorGameLastLv" .. PlayerModel:getUid()]
end

function P:setColorGameLastLv(lv)
	self.saveData["colorGameLastLv" .. PlayerModel:getUid()] = lv
	self:onSave()
end

function P:getColorGameLastChipIndex()
	return self.saveData["colorGameLastChipIndex" .. PlayerModel:getUid()]
end

function P:setColorGameLastChipIndex(chipIndex)
	self.saveData["colorGameLastChipIndex" .. PlayerModel:getUid()] = chipIndex
	self:onSave()
end

function P:getColorGameLastBets()
	local list = {}
	if not self.saveData["colorGameLastBets" .. PlayerModel:getUid()] then
		return list
	end
	for k, v in pairs(self.saveData["colorGameLastBets" .. PlayerModel:getUid()]) do
		table.insert(list, {id = v.id, value = v.value})
	end
	return list
end

function P:setColorGameLastBets(lastBets)
	local list = {}
	for k, v in pairs(lastBets) do
		table.insert(list, {id = v.id, value = v.value})
	end
	self.saveData["colorGameLastBets" .. PlayerModel:getUid()] = list
	self:onSave()
end

return P