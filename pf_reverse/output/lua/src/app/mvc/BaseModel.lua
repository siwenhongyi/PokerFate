
--基础model类
local P = class("BaseModel")
BaseModel=P
function P:ctor(name)
	self._model_name = name or self.__cname
	if self.saveData and self.saveData.cloud then
		self.__cloud = clone(self.saveData.cloud)
	end
	if self.saveData then
		self.__original = clone(self.saveData)
	end
    self:loadLocalData()
	self:initListeners()
end

function P:loadLocalData()
	if self._load then return end

	local jstr = LocalStore:getStringForKey(self._model_name)
	if jstr and string.len(jstr) > 1 then
		if not bee.isRelease then
			print(self._model_name.." 存储信息" .. jstr)
		end
		--print("读缓存数据")
		local d = json.decode(jstr)
		if d then
			for k, v in pairs(self.saveData or {}) do
				if d[k]==nil then
					d[k]=v
					if not bee.isRelease then
						CS.NLog.Log(CS.UnityEngine.Color.red, self._model_name.." 兼容一个新加的结构self.saveData."..k)
					end
				end
			end
			
			self.saveData = d
		end
	else
		--print("首次读配置")
	end
	self:updateCloudData()
	self._load=true
end

function P:updateCloudData()
	if self.__cloud then
		local d = ModelManager:getCloudData(self._model_name, self.isSubCloud)
		for k, v in pairs(self.__cloud) do
			if nil == d[k] then
				d[k] = clone(v)
			end
		end
		self.saveData.cloud = d
		self.cloud = self.saveData.cloud
	end
end

-- 初始化数据成功后，这个函数里可以安全访问其它 model
function P:afterInit()
end

-- websocket 登录成功后调用
function P:afterLogin()
end

function P:getCloudKeyData(key)
	if not self.cloud[key .. PlayerModel:getUid()] then
        self.cloud[key .. PlayerModel:getUid()] = {}
    end
	return self.cloud[key .. PlayerModel:getUid()]
end

function P:initListeners()
	local bindMap = self:excludebindMapFun()
	self._eventListeners = {}
	for funcName in pairs(getmetatable(self).__index) do
		if not bindMap[funcName] then
			if string.find(funcName,"evt_") then
				bee.on(funcName, self[funcName], self)
				self._eventListeners[#self._eventListeners+1] = funcName
			end
		end
	end
	bee.on("evt_onApplicationQuit", self["evt_onApplicationQuit"], self)
	self._eventListeners[#self._eventListeners+1] = "evt_onApplicationQuit"
end

-- 清除
function P:__clearListeners()
	if self._eventListeners then
		for _, event in ipairs(self._eventListeners) do
			bee.off(event, self[event],self)
		end
		self._eventListeners = nil
	end
end

--清掉缓存需要重新初始化数据
function P:clear()
    self:__clearListeners()
	self.saveData = nil
	self.multifileData = nil
end

--永久清掉本地数据 慎用
function P:clearData()
	LocalStore:deleteValueForKey(self._model_name)
	if self.saveData then
		for k, v in pairs(self.saveData) do
			if k == "cloud" then
			else
				self.saveData[k] = nil
			end
		end
		for k, v in pairs(self.__original) do
			if k == "cloud" then
			elseif type(v)=="table" then
				self.saveData[k] = clone(v)
			else
				self.saveData[k] = v
			end		
		end
	end
	if self.cloud then
		for k, v in pairs(self.cloud) do
			self.cloud[k] = nil
		end
		for k, v in pairs(self.__cloud) do
			if type(v)=="table" then
				self.cloud[k] = clone(v)
			else
				self.cloud[k] = v
			end		
		end
	end
	self:updateCloudData()

	if PlayerModel and PlayerModel:isLogin() then
		self:afterLogin()
	end
end


function P:excludebindMapFun()
	return  {}
end

function P:evt_onApplicationQuit()
	self:onSave()
end

function P:evt_onActivityDestroy()
	print("evt_onActivityDestroy")
	self:onSave()
end

function P:evt_onActivityResume()
	--self:onSave()
end

function P:evt_onActivityPause()
	--print("evt_onActivityPause")
	self:onSave()
end

function P:onSave()
	if not self.saveData then
		return 
	end
	self._isDirty = true
	if bee.isPc then
		for k, v in pairs(self.saveData) do
			if type(k)=="number" then
				printError(self._model_name.."存储格式中包含了整数的 Key: "..k)
			end
		end
		if self.saveData.cloud then
			if (not self.isSubCloud and self.saveData.cloud ~= ModelManager._cloud[self._model_name]) or (self.isSubCloud and self.saveData.cloud ~= ModelManager._subCloud[self._model_name]) then
				printError("[" .. self._model_name .. "] 云端数据表变为临时表，无法上报！" .. debug.traceback())
			end
		end
	end
    -- LocalStore:setStringForKey(self._model_name, saveStr)
end

-- 执行存盘
function P:doSave()
	if self._isDirty and self.saveData then
		local cloud = self.saveData.cloud
		self.saveData.cloud = nil
		local saveStr = json.encode(self.saveData)
		self.saveData.cloud = cloud
		LocalStore:setStringForKey(self._model_name, saveStr)
		self._isDirty = false
		return true
	end
	return false
end

--首次安装上报一次上数据
function P:reporInitData()
end

function P:downloadData()
end

function P:uploadData()
end

return BaseModel
