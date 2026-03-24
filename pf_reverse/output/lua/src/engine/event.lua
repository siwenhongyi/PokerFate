-- 事件机制

-- 向物体 obj 的类发射事件
bee.emitTo = function(obj, name, params, p2, p3)
    local cls = ObjectPool:getCls(obj)
    if cls then
        cls:emit(name, params, p2, p3)
    else
    	if not bee._waitObjEvts then
    		bee._waitObjEvts = {}
    	end
    	bee._waitObjEvts[obj] = {obj, name, params, p2, p3}
    end
end

bee.popObjEmit = function(obj, needEmit)
	if bee._waitObjEvts and obj then
		local evt = bee._waitObjEvts[obj]
		if evt then
			bee._waitObjEvts[obj] = nil
			if needEmit then
				bee.emitTo(unpack(evt))
			end
		end
	end
end

bee.invoke = function(obj, funcName, ...)
	local cls = ObjectPool:getCls(obj)
	if cls and cls[funcName] then
		return cls[funcName](cls, ...)
	end
end

-- 发射全局事件
bee.emit = function(name, params, p2, _t)
	if bee._emiting then
		if not bee._waitEvts then
			bee._waitEvts = {{name, params, p2, _t}}
		else
			bee._waitEvts[#bee._waitEvts + 1] = {name, params, p2, _t}
		end
		if bee.isEditor then
			bee._waitEvts[#bee._waitEvts][4] = debug.traceback()
		end
		return
	end
	if bee._evts then
		local evts = bee._evts[name]
		if evts then
			bee._emiting = name
			if bee.isEditor then
				for _, v in ipairs(evts) do
					if v[2] then
						v[1](v[2], params, p2)
					else
						v[1](params, p2)
					end
				end
			else
				local _, err = pcall(function()
					for _, v in ipairs(evts) do
						if v[2] then
							v[1](v[2], params, p2)
						else
							v[1](params, p2)
						end
					end
				end)
				if err then
					printError("[bee.event] emit event error ", name, err, _t)
				end
			end
			bee._emiting = nil
		end
		if bee._addEvts then
			for _, v in ipairs(bee._addEvts) do
				bee.on(v[1], v[2], v[3])
			end
			bee._addEvts = nil
		end
		if bee._delEvts then
			for _, v in ipairs(bee._delEvts) do
				bee.off(v[1], v[2], v[3])
			end
			bee._delEvts = nil
		end
	end
end

bee.on = function(name, func, obj)
	if not name or not func then
		print("bee register event no name or func ")
		return
	end
	if not bee._evts then
		bee._evts = {}
	end
	if bee._emiting then
		if not bee._addEvts then
			bee._addEvts = {{name, func, obj}}
		else
			bee._addEvts[#bee._addEvts + 1] = {name, func, obj}
		end
	else
		local evts = bee._evts[name]
		if not evts then
			evts = {}
			bee._evts[name] = evts
		end
		evts[#evts + 1] = {func, obj}
	end
end

bee.off = function(name, func, obj)
	if bee._emiting == name then
		if not bee._delEvts then
			bee._delEvts = {{name, func, obj}}
		else
			bee._delEvts[#bee._delEvts + 1] = {name, func, obj}
		end
	else
		if bee._evts and bee._evts[name] then
			local evts = bee._evts[name]
			for k, v in ipairs(evts) do
				if v[1] == func and v[2] == obj then
					table.remove(evts, k)
					break
				end
			end
		end
	end
end

bee.offAll = function()
    bee._evts = nil
end

bee._emitWaitEvt = function()
	if bee._waitEvts and #bee._waitEvts > 0 then
		local d = table.remove(bee._waitEvts, 1)
		bee.emit(d[1], d[2], d[3], d[4])
	end
end
