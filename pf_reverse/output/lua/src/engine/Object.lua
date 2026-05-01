-- GameObect 的 Lua 绑定类
local P = class("Object")
Object = P

function P:ctor(params)
	self._ui = {}
	self.node = nil
	self.transform = nil
	self._evts = nil
end

function P:addUi(obj)
	self._ui[obj.name] = obj
end

function P:setParams(params)
	self._params = params
end

function P:getParams()
	return self._params
end

function P:onDestroy()
	if self._beeTag then
		for _, v in ipairs(self._beeTag) do
			bee.off(v[1], v[2])
		end
	end
end

function P:destroy()
    if self.node then
        CU.GameObject.Destroy(self.node)
        self.node = nil
    end
end

function P:getChildCount()
	if self.transform then
		return self.transform.childCount
	end
	if self.node then
		return self.node.transform.childCount
	end
	return 0
end

function P:getChild(i)
	if self.transform then
		return self.transform:GetChild(i)
	end
	if self.node then
		return self.node.transform:GetChild(i)
	end
	return nil
end

-- 查找子物体，parent：父物体，可不传
function P:find(name, parent)
    local t = nil
	if parent then
		t = parent.transform:Find(name)
	elseif self.transform then
		t = self.transform:Find(name)
	elseif self.node then
		t = self.node.transform:Find(name)
	end
    if t then
        return t.gameObject
    end
	return nil
end

function P:removeAllChildren(parent)
	if parent then
		for i = 0, parent.transform.childCount - 1 do
			CU.GameObject.Destroy(parent.transform:GetChild(i).gameObject)
		end
		parent.transform:DetachChildren()
	end
end

-- 延迟执行一次 cb
function P:once(dt, cb)
	if bee.isNull(self.node) then
		return 0
	end
	return bee.once(dt, cb, self.node)
end

-- 延迟执行 num 次 cb
function P:repeatN(num, dt, cb)
	if bee.isNull(self.node) then
		return 0
	end
	return bee.repeatN(num, dt, cb, self.node)
end

-- 延迟循环执行 cb
function P:schedule(dt, cb)
	if bee.isNull(self.node) then
		return 0
	end
	return bee.schedule(dt, cb, self.node)
end

-- 注册 bee 全局事件，在物体销毁时自动注销
function P:onEvent(name, func)
	bee.on(name, func)
	if not self._beeTag then
		self._beeTag = {{name, func}}
	else
		self._beeTag[#self._beeTag + 1] = {name, func}
	end
end

-- 注册自身节点事件
function P:on(name, func)
	if not name or not func then
		print("register event no name or func ", self.__cname)
		return
	end
	if not self._evts then
		self._evts = {}
	end
	local evts = self._evts[name]
	if not evts then
		evts = {}
		self._evts[name] = evts
	end
	if self._emiting then
		if not self._addEvts then
			self._addEvts = {{name, func}}
		else
			self._addEvts[#self._addEvts + 1] = {name, func}
		end
	else
		evts[#evts + 1] = func
	end
end

-- 注销自身节点事件
function P:off(name, func)
	if self._emiting then
		if not self._delEvts then
			self._delEvts = {{name, func}}
		else
			self._delEvts[#self._delEvts + 1] = {name, func}
		end
	else
		if self._evts and self._evts[name] then
			local evts = self._evts[name]
			for k, v in ipairs(evts) do
				if v == func then
					table.remove(evts, k)
					break
				end
			end
		end
	end
end

function P:offAll()
	self._evts = nil
end

-- 向本节点发射事件 未实现
function P:emit(name, params, p2, p3)
	-- print(json.encode(self._evts))
	if self._evts then
		local evts = self._evts[name]
		if evts then
			self._emiting = true
			for _, v in ipairs(evts) do
				v(params, p2, p3)
			end
			self._emiting = nil
		end
		if self._addEvts then
			for _, v in ipairs(self._addEvts) do
				self:on(v[1], v[2])
			end
			self._addEvts = nil
		end
		if self._delEvts then
			for _, v in ipairs(self._delEvts) do
				self:off(v[1], v[2])
			end
			self._delEvts = nil
		end
	end
end

function P:invoke(obj, fnName, ...)
    local cls = ObjectPool:getCls(obj)
    if cls and cls[fnName] then
        cls[fnName](cls, ...)
    end
end

--自动绑定事件
function P:addAutoEvent()
	if self._eventListeners then return end
	local bindMap = self:excludebindMapFun() or {}
	self._eventListeners = {}
	self:__addAutoEvent(getmetatable(self).__index, bindMap)
	
	if self.super ~= P then
		self:__addAutoEvent(self.super, bindMap)
	end
	local parent = self.super.super
	while parent and parent ~= P do
		self:__addAutoEvent(parent, bindMap)
		parent = parent.super
	end

	bee.popObjEmit(self.node, true)
end

function P:__addAutoEvent(cls, bindMap)
	if cls.__cname ~= "Object" and cls.__cname ~= "UiBase" then
		for funcName in pairs(cls) do
			if not bindMap or not bindMap[funcName] then
				-- print("addAutoEvent",funcName, cls.__cname)
				if string.find(funcName,"evt_") then
					bindMap[funcName] = true
					bee.on(funcName, self[funcName], self)
					self._eventListeners[#self._eventListeners+1] = funcName
				end
			end
		end
	end
end

-- 删除所有侦听的事件
function P:removeAutoEvent()
	if self._eventListeners then
		for _, event in ipairs(self._eventListeners) do
			bee.off(event, self[event], self)
		end
		self._eventListeners = nil
	end

	bee.popObjEmit(self.node)
end

----------------继承重写---------------------
-- [子类重写] 排除的自动绑定的方法  ctor 之后
function P:excludebindMapFun()
	return nil
end

return P