---@class UIDUtil
local M = {}

local _uid = 0
local _eventId = 1000000000
local _configId = 0
local _redPointId = 0
local _itemAmountUid = 0

UIDUtil = M

--获取全局唯一的id（一般可以用这个)
function M.getUID()
	_uid = _uid + 1
	return _uid
end

--事件名的唯一id
function M.getEventUID()
	_eventId = _eventId + 1
	return _eventId
end

--配置的唯一id
function M.getConfigUID()
	_configId = _configId + 1
	return _configId
end

--红点的唯一id
function M.getRedPointUID()
	_redPointId = _redPointId + 1
	return _redPointId
end

--数量监控的唯一id
function M.getAmountUID()
	_itemAmountUid = _itemAmountUid + 1
	return _itemAmountUid
end
