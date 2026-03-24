-- GameObject 绑定池
local P = {
    curObj = nil,   -- 当前操作物体
    _objects = {},  -- 已经绑定的物体列表
	clsName = nil,
}
ObjectPool = P

function P:bindObj(obj, cls)
    self._objects[obj] = cls
end

function P:unbindObj(obj)
    self._objects[obj] = nil
end

function P:bind(clsName)
    if self.curObj then
        clsName = clsName or self.clsName
		local _, err = pcall(function()
            local cls = require(clsName)
            if cls then
                local params = self:getBindParams()
                local c = cls:create(params)
                c.node = self.curObj
                c.transform = c.node.transform
                self._objects[c.node] = c
            end
		end)
		if err then
			printError("[ObjectPool] bindCurUi error", clsName, err)
		end
    end
end

function P:getBindParams()
    local params = nil
    if self.arg1 and "" ~= self.arg1 then
        params = json.decode(self.arg1)
        self.arg1 = nil
    end
    if self.arg2 and "" ~= self.arg2 then
        if not params then
            params = json.decode(self.arg2)
        else
            local tmp = json.decode(self.arg2)
            for k, v in pairs(tmp) do
                params[k] = v
            end
        end
        self.arg2 = nil
    end
    return params
end

function P:bindObjToUi()
	if self.curObj and self._bindObj then
		local c = ObjectPool:getCls(self.curObj)
		if c then
			c:addUi(self._bindObj)
			self._bindObj = nil
		end
	end
end

function P:onAwake()
	-- if self.curObj then
	-- 	local c = ObjectPool:getCls(self.curObj)
	-- 	if c then
	-- 		if c.addAutoEvent then c:addAutoEvent() end
	-- 	end
	-- end
    self:invoke("onAwake", 0)
end

function P:onEnable()
	if self.curObj then
		local c = ObjectPool:getCls(self.curObj)
		if c then
			if c.addAutoEvent and not c._watiStart then c:addAutoEvent() end
			if c.onEnable then c:onEnable() end
		end
	end
end

function P:onStart()
    self:invoke("onStart", 0)
end

function P:onUpdate()
    if scheduler then
        self.arg1 = scheduler.dt
    else
        self.arg1 = 1 / 60
    end
    self:invoke("onUpdate", 1)
end

function P:onDisable()
	if self.curObj then
		local c = ObjectPool:getCls(self.curObj)
		if c then
			if c.removeAutoEvent then c:removeAutoEvent() end
			if c.onDisable then c:onDisable() end
		end
	end
end

function P:onDestroy()
	if self.curObj then
        local node = self.curObj
        local obj = self._objects[node]
        if obj and obj.onDestroy then
            self._objects[node]:onDestroy()
            self._objects[node] = nil
        end
        if obj then obj.node = nil end
        if self.curObj == node then
		    self.curObj = nil
        end
	end
end

function P:invoke(funcName, argCount)
    if self.curObj then
        local obj = self._objects[self.curObj]
        if obj and obj[funcName] then
            if not argCount or 0 == argCount then
                obj[funcName](obj)
            elseif 1 == argCount then
                obj[funcName](obj, self.arg1)
            elseif 2 == argCount then
                obj[funcName](obj, self.arg1, self.arg2)
            elseif 3 == argCount then
                obj[funcName](obj, self.arg1, self.arg2, self.arg3)
            elseif 4 == argCount then
                obj[funcName](obj, self.arg1, self.arg2, self.arg3, self.arg4)
            elseif 5 == argCount then
                obj[funcName](obj, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5)
            elseif 6 == argCount then
                obj[funcName](obj, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg6)
            elseif 7 == argCount then
                obj[funcName](obj, self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg7)
            end
            self.arg1, self.arg2, self.arg3, self.arg4, self.arg5, self.arg7 = nil, nil, nil, nil, nil, nil
        end
    end
end

function P:getCls(obj)
    return self._objects[obj]
end

function P:onI18n(text)
    if self.curObj and _T then
        local cmp = self.curObj:GetComponent("Text") or self.curObj:GetComponent("TextMeshProUGUI")
        if cmp then
            local s = nil
            if text then
                s = _T(text)
                cmp.text = s
            else
                s = _T(cmp.text)
                cmp.text = s
            end
            cmp.font = getTextFont(s, cmp)
        end
    end
end

function P:onI18n2(text)
    if self.curObj and _T then
        local cmp = self.curObj:GetComponent("Text") or self.curObj:GetComponent("TextMeshProUGUI")
        if cmp then
            local s = nil
            if text then
                s = _T(text, lan)
                if lan ~= "en" then
                    s = string.gsub(s, " ",  Config.NO_WRAP_SPACE)
                end
                cmp.text = s
            else
                s = _T(cmp.text, lan)
                if lan ~= "en" then
                    s = string.gsub(s, " ",  Config.NO_WRAP_SPACE)
                end
                cmp.text = s
            end
            cmp.font = getTextFont(s, cmp)
        end
    end
end

function P:onI18Img(key, autoSize)
    if self.curObj and _I then
        local img = _I(key)
        if img == key then
            local ks = string.split(key, "_")
            if #ks > 2 then
                local preKey = ks[1]:gsub("^%l", string.upper)
                if preKey == "Ingame" then
                    preKey = "InGame"
                end
                key = string.gsub(key, "%(Clone%)", '')
                img = string.format("%s[%s]", preKey, string.sub(key, 1, #key - 3) .. "_" .. LAN:getLanguage())
            end
        end
        bee.setIconInAtlas(self.curObj, img, autoSize == true)
    end
end

function P:onI18ImgAS(key)
    self:onI18Img(key, true)
end

function bee.invokePool(funcName, argCount)
    if P[funcName] then
        P[funcName](P)
    else
        P:invoke(funcName, argCount)
    end
end

