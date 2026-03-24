local P = {
	_isDirty = false,
	_cloud = {},		-- 云端数据
	_subCloud = {},		-- k-v 格式存储的云端数据
	_isCanUpload = false,	-- 是否能够上传云端数据了，防止在拉取数据前上传污染数据源
	_saveEt = 0,
}
ModelManager = P
local gamePath = {
	{name = "LoginModel", cls = require "app.model.LoginModel"},
	{name = "SdkModel", cls = require "app.model.SdkModel"},
	{name = "ShopModel", cls = require "app.model.ShopModel"},
	
	{name = "ActivityManager", cls = require "app.model.activity.ActivityManager"},
	{name = "ItemModel", cls = require "app.model.ItemModel"},
    {name = "VipModel", cls = require "app.model.VipModel"},
    {name = "PlayerModel", cls = require "app.model.PlayerModel"},
    {name = "CharacterModel", cls = require "app.model.CharacterModel"},
    {name = "GachaModel", cls = require "app.model.GachaModel"},
    {name = "GameModel", cls = require "app.model.GameModel"},
    {name = "SettingModel", cls = require "app.model.SettingModel"},
    {name = "FriendModel", cls = require "app.model.FriendModel"},
    {name = "EmailModel", cls = require "app.model.EmailModel"},
    {name = "NoticeModel", cls = require "app.model.NoticeModel"},
    {name = "StoryModel", cls = require "app.model.StoryModel"},
    {name = "TaskModel", cls = require "app.model.TaskModel"},
    {name = "SevenDayTaskModel", cls = require "app.model.SevenDayTaskModel"},
    {name = "ShareModel", cls = require "app.model.ShareModel"},
    {name = "RankingModel", cls = require "app.model.RankingModel"},
    {name = "TournamentModel", cls = require "app.model.TournamentModel"},
    {name = "SideGameModel", cls = require "app.model.SideGameModel"},

    {name = "ActivityModel", cls = require "app.model.ActivityModel"},
    {name = "ActivityNewmanCheckinModel", cls = require "app.model.activity.ActivityNewmanCheckinModel"},
    {name = "SignInModel", cls = require "app.model.SignInModel"},
    {name = "ThemeModel", cls = require "app.model.activity.ThemeModel"},
	{name = "SpringFestivalModel", cls = require "app.model.activity.SpringFestivalModel"},
	
    
}

local allPath={}
table.addRange(allPath,gamePath)

function P:init()
	self:loadCloud()
    for _, v in pairs(gamePath) do
        if (not P[v.name]) then
            P[v.name] = v.cls.new()
			rawset(_G, v.name, P[v.name])
        end
    end
	for _, v in pairs(gamePath) do
		if self[v.name] then
			self[v.name]:afterInit()
		end
	end
end

function P:_getInitCloud()
	return {udv = G_DATA_VERSION}
end

function P:onSave()
	-- 不需要存本地的表
	local excludeTable = 
	{
	   {name = "FriendChatModel"},
	   --{name = "PlayerModel"},
	   {name = "ItemModel"},
    }
	for _, v in pairs(allPath) do
		if (not excludeTable[v.name] and P[v.name]) then
			if P[v.name].onSave then P[v.name]:onSave() end		
		end
	end
end

function P:afterLogin()
	for _, v in pairs(allPath) do
		if P[v.name].afterLogin then
			P[v.name]:afterLogin()
		end
	end
end

function P:afterLogout()
	for _, v in pairs(allPath) do
		if P[v.name].afterLogout then
			P[v.name]:afterLogout()
		end
	end
end

-- 切换帐号时的清理
function P:clear(Rebuild)
    -- 不需要清理的表
	self:clearCloudData()
    local excludeTable = 
	{
		"LoginModel",
		"ServerModel",
		"SdkModel",
	}
	PlayerModel = nil
    for _, v in pairs(allPath) do
        if (not table.contains(excludeTable,v.name) and P[v.name]) then
			print("P:clear",v.name)
            if P[v.name].clear then P[v.name]:clear() end
            if not Rebuild then
			   P[v.name] = nil 		
			else
			   P[v.name] = v.cls.new(true)
			   rawset(_G, v.name, P[v.name])
			end		
        end
    end
	if Rebuild then
		for _, v in pairs(allPath) do
			if self[v.name] then
				self[v.name]:afterInit()
			end
		end
	end
end

-- 永久清掉某个模块数据 慎用
function P:clearData(modelName)

	print("清理"..modelName.."~~~")
	if P[modelName].clearData then 
		P[modelName]:clearData() 
		--P[v.name] = v.cls.new()
	end
end


--向服务端同步一次客户端初始数据
function P:reporInitData()
	for k, v in pairs(allPath) do
		if P[v.name] and P[v.name].reporInitData then
			P[v.name]:reporInitData()
		end
	end
	
	self._dirtySub = self._subCloud
	self:uploadCloudData()
end


function P:downloadAllData(cb)
	self:downloadCloudData(function(ret)
		self:setIsCanUpload(true)
		if ret then
			self._isDirty = false
			for k, v in pairs(allPath) do
				if P[v.name] then
					P[v.name]:updateCloudData()
				end
			end
			for k, v in pairs(allPath) do
				if P[v.name] then
					P[v.name]:afterInit()
				end
			end
		end
		if cb then
			cb(ret)
		end
	end)
end

--向服务端同步一次断网的时候没有同步过的只能同步一次的数据
function P:reporOfflineData()
	for k, v in pairs(allPath) do
		--print("reporInitData",v.name)
		if P[v.name] then
			if P[v.name].reporOfflineData then
				P[v.name]:reporOfflineData()
			end
		end
	end
end

function P:loginPlayerDataInit(data)
    for _, v in pairs(allPath) do
        if P[v.name] and P[v.name].loginPlayerDataInit then
            P[v.name]:loginPlayerDataInit(data)
        end
    end
end

function P:loginPlayerDataFinish(data)
    for _, v in pairs(allPath) do
        if P[v.name] and P[v.name].loginPlayerDataFinish then
            P[v.name]:loginPlayerDataFinish(data)
        end
    end
end

function P:downloadData(name,finished)
	local reportJson={fn = name}
	Net:send("UserIF","DownloadData",reportJson,function (data)
			if data.code==0 then
				finished(data.data, data.dataMap)
			else
				finished(nil, nil)
			end
		end)
end

function P:uploadData(name, req, dataMap)
	local reportJson={
		fn = name,
		data = (req and json.encode(req) or nil),
		uid = PlayerModel and PlayerModel:getUid(),
	}
	if dataMap then
		reportJson.dataMap = {}
		for k, v in pairs(dataMap) do
			reportJson.dataMap[k] = json.encode(v)
		end
	end
	if bee.isPc then
		print("uploadData",reportJson.data)
	end
	if name == "ModelManager" then
		if bee.isPc then
			print("ModelManager uploadData", name, reportJson.data, json.encode(dataMap), debug.traceback())
		end
	end
	Net:send("UserIF","UploadData",reportJson,function (data)
			if data.code==0 then
				-- print("updateLang Suc")
			end
		end)
end

function P:getCloudData(name, isSub)
	if isSub then
		if self._subCloud[name] then
			return self._subCloud[name]
		end
		if self._cloud[name] then
			self._subCloud[name] = self._cloud[name]
			self._cloud[name] = nil
		else
			self._subCloud[name] = {}
		end
		return self._subCloud[name]
	end
	if self._cloud[name] then
		return self._cloud[name]
	end
	self._cloud[name] = {}
	return self._cloud[name]
end

function P:uploadCloudData()
	if self._isDirty then
		self._isDirty = false
		self:uploadData("ModelManager", self._cloud, self._dirtySub)
		self._dirtySub = nil
	end
end

function P:downloadCloudData(cb)
	self:downloadData("ModelManager", function(data, dataMap)
		local _cloud, ret = nil, true
		if data and "" ~= data then
			_cloud = json.decode(data)
		else
			-- self._cloud = {}
		end
		if _cloud and _cloud.udv == G_DATA_VERSION then
			self._cloud = _cloud
			if dataMap and "" ~= dataMap then
				for k, v in pairs(dataMap) do
					self._subCloud[k] = json.decode(v) or {}
				end
			end
		else
			ret = false
			-- self._cloud = self:_getInitCloud()
			-- self._subCloud = {}
			-- RedManager:clearData()
		end
		if cb then
			cb(ret)
		end
	end)
end

function P:clearCloudData()
	self._isCanUpload=false
	self._cloud = self:_getInitCloud()
	self._subCloud = {}
end

function P:saveCloud()
	local saveStr = json.encode(self._cloud)
	LocalStore:setStringForKey("ModelManager", saveStr)
end

function P:saveSubCloud()
	local saveStr = json.encode(self._subCloud)
	LocalStore:setStringForKey("ModelManager_Sub", saveStr)
end

function P:loadCloud()
	local jstr = LocalStore:getStringForKey("ModelManager")
	if jstr and string.len(jstr) > 1 then
		self._cloud = json.decode(jstr) or self:_getInitCloud()
	end
	jstr = LocalStore:getStringForKey("ModelManager_Sub")
	if jstr and string.len(jstr) > 1 then
		self._subCloud = json.decode(jstr) or {}
	end
	if self._cloud.udv ~= G_DATA_VERSION then
		self._cloud = self:_getInitCloud()
		self._subCloud = {}
		-- LocalStore:DeleteAll()
		-- RedManager:clearData()
	end
end

function P:addDirtySubCloud(name)
	if not self._dirtySub then
		self._dirtySub = {}
	end
	self._dirtySub[name] = self._subCloud[name]
end

function P:setIsCanUpload(flag)
	self._isCanUpload = flag
end

function P:useServerData(cb)
	--新方法同步数据 model 里面带cloud字段的结构都会自动进行一次同步
	UiManager:showUI("MainLockTouch", {dt = 3})
	self:downloadAllData(function(ret)
		UiManager:hideUI("MainLockTouch")
		if PlayerModel then
			PlayerModel:resetLowData()
		end
		if ret then
			self._isDirty = false
			self._dirtySub = nil

			self:saveCloud()
			self:saveSubCloud()
			
			if cb then cb() end

			bee.removeTasks()
			bee.enterSceneEx("MainScene")

			ShopModel:updateServerShopRecord()
		end
	end)
end

function P:useLocalData(cb)
	self:reporInitData()
	self:setIsCanUpload(true)
	if PlayerModel then
		PlayerModel:resetLowData()
	end
	self._isDirty = false
	self._dirtySub = nil
	if cb then cb() end
end

bee.addUpdater(function(dt)
	local m, dirty, subCloud = nil, false, nil
	for k, v in pairs(allPath) do
		m = P[v.name]
		if m then
			if m:doSave() and m.__cloud then
				P._isDirty = true
				if m.isSubCloud then
					P:addDirtySubCloud(m._name)
					subCloud = true
				else
					dirty = true
				end
			end
		end
	end
	if dirty then
		P:saveCloud()
	end
	if subCloud then
		P:saveSubCloud()
	end
	if P._isCanUpload and P._isDirty then
		P._saveEt = P._saveEt + dt
		if P._saveEt >= Config.NET_SYNC_TIME then
			P._saveEt = 0
			if PlayerModel and PlayerModel:isLogin() and not PlayerModel:isLowData() then
				P:uploadCloudData()
				if PlayerModel then
					PlayerModel:doReportPlayerData()
				end
			end
		end
	end
end)

return P
