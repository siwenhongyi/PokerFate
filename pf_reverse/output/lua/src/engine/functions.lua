--[[

Copyright (c) 2014-2017 Chukong Technologies Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

]]

function printLog(tag, fmt, ...)
    local t = {
        "[",
        string.upper(tostring(tag)),
        "] ",
        string.format(tostring(fmt), ...)
    }
    print(table.concat(t))
end

function printError(...)
    CU.Debug.LogError(table.concat{...})
    -- printLog("ERR", fmt, ...)
    -- print(debug.traceback("", 2))
end

-- @function: 打印table的内容，递归
-- @param: tbl 要打印的table
-- @param: level 递归的层数，默认不用传值进来
-- @param: filteDefault 是否过滤打印构造函数，默认为是
-- @return: return
function printTable(tbl)
	local cache = {
		[tbl] = "./"
	}
	local isreturn = false

	local function print_f(tbl, level, filteDefault)
		if isreturn then
			return
		end
		for k, v in pairs(tbl) do
			if k == "_parent_message" then
				print(tostring(v))
				isreturn = true
				return
			end
		end
		local msg = ""
		filteDefault = filteDefault or true -- 默认过滤关键字
		level = level or 1
		local indent_str = ""
		for i = 1, level do
			indent_str = indent_str .. "\t"
		end

		CS.NLog.Log(CS.UnityEngine.Color.green,indent_str .. "{")
		for k, v in pairs(tbl) do
			if filteDefault then
				if k ~= "_type_checker" and k ~= "_listener" then
					local item_str = string.format("%s[%s] = [%s]", indent_str .. "\t", tostring(k), tostring(v))
					CS.NLog.Log(CS.UnityEngine.Color.green,item_str)
					if type(v) == "table" then
						if cache[v] then
							CS.NLog.Log(CS.UnityEngine.Color.green,string.format("%s[%s] = [%s]", indent_str .. " ", tostring(k), cache[v]))
						else
							cache[v] = k
							print_f(v, level + 1)
						end
					end
				end
			else
				local item_str = string.format("%s[%s] = [%s]", indent_str .. " ", tostring(k), tostring(v))
				CS.NLog.Log(CS.UnityEngine.Color.green,item_str)
				if type(v) == "table" then
					if cache[v] then
						CS.NLog.Log(CS.UnityEngine.Color.green,string.format("%s[%s] = [%s]", indent_str .. " ", tostring(k), cache[v]))
					else
						cache[v] = k
						print_f(v, level + 1)
					end
				end
			end
		end
		CS.NLog.Log(CS.UnityEngine.Color.green,indent_str .. "}")
	end

	CS.NLog.Log(CS.UnityEngine.Color.green,"/***************打印表******************/")
	print_f(tbl)
	CS.NLog.Log(CS.UnityEngine.Color.green,"/***************打印表end******************/")
end

function printInfo(fmt, ...)
    if type(DEBUG) ~= "number" or DEBUG < 2 then return end
    printLog("INFO", fmt, ...)
end

local function dump_value_(v)
    if type(v) == "string" then
        v = "\"" .. v .. "\""
    end
    return tostring(v)
end

function dump(value, description, nesting)
    if type(nesting) ~= "number" then nesting = 3 end

    local lookupTable = {}
    local result = {}

    local traceback = string.split(debug.traceback("", 2), "\n")
    print("dump from: " .. string.trim(traceback[3]))

    local function dump_(value, description, indent, nest, keylen)
        description = description or "<var>"
        local spc = ""
        if type(keylen) == "number" then
            spc = string.rep(" ", keylen - string.len(dump_value_(description)))
        end
        if type(value) ~= "table" then
            result[#result +1 ] = string.format("%s%s%s = %s", indent, dump_value_(description), spc, dump_value_(value))
        elseif lookupTable[tostring(value)] then
            result[#result +1 ] = string.format("%s%s%s = *REF*", indent, dump_value_(description), spc)
        else
            lookupTable[tostring(value)] = true
            if nest > nesting then
                result[#result +1 ] = string.format("%s%s = *MAX NESTING*", indent, dump_value_(description))
            else
                result[#result +1 ] = string.format("%s%s = {", indent, dump_value_(description))
                local indent2 = indent.."    "
                local keys = {}
                local keylen = 0
                local values = {}
                for k, v in pairs(value) do
                    keys[#keys + 1] = k
                    local vk = dump_value_(k)
                    local vkl = string.len(vk)
                    if vkl > keylen then keylen = vkl end
                    values[k] = v
                end
                table.sort(keys, function(a, b)
                    if type(a) == "number" and type(b) == "number" then
                        return a < b
                    else
                        return tostring(a) < tostring(b)
                    end
                end)
                for i, k in ipairs(keys) do
                    dump_(values[k], k, indent2, nest + 1, keylen)
                end
                result[#result +1] = string.format("%s}", indent)
            end
        end
    end
    dump_(value, description, "- ", 1)

    for i, line in ipairs(result) do
        print(line)
    end
end

function printf(fmt, ...)
    print(string.format(tostring(fmt), ...))
end

function checknumber(value, base)
    return tonumber(value, base) or 0
end

function checkint(value)
    return math.round(checknumber(value))
end

function checkbool(value)
    return (value ~= nil and value ~= false)
end

function checktable(value)
    if type(value) ~= "table" then value = {} end
    return value
end

function isset(hashtable, key)
    local t = type(hashtable)
    return (t == "table" or t == "userdata") and hashtable[key] ~= nil
end

local setmetatableindex_
setmetatableindex_ = function(t, index)
    if type(t) == "userdata" then
        local peer = tolua.getpeer(t)
        if not peer then
            peer = {}
            tolua.setpeer(t, peer)
        end
        setmetatableindex_(peer, index)
    else
        local mt = getmetatable(t)
        if not mt then mt = {} end
        if not mt.__index then
            mt.__index = index
            setmetatable(t, mt)
        elseif mt.__index ~= index then
            setmetatableindex_(mt, index)
        end
    end
end
setmetatableindex = setmetatableindex_

function clone(object)
    local lookup_table = {}
    local function _copy(object)
        if type(object) ~= "table" then
            return object
        elseif lookup_table[object] then
            return lookup_table[object]
        end
        local newObject = {}
        lookup_table[object] = newObject
        for key, value in pairs(object) do
            newObject[_copy(key)] = _copy(value)
        end
        return setmetatable(newObject, getmetatable(object))
    end
    return _copy(object)
end

function class(classname, ...)
    local cls = {__cname = classname}

    local supers = {...}
    for _, super in ipairs(supers) do
        local superType = type(super)
        assert(superType == "nil" or superType == "table" or superType == "function",
            string.format("class() - create class \"%s\" with invalid super class type \"%s\"",
                classname, superType))

        if superType == "function" then
            assert(cls.__create == nil,
                string.format("class() - create class \"%s\" with more than one creating function",
                    classname));
            -- if super is function, set it to __create
            cls.__create = super
        elseif superType == "table" then
            if super[".isclass"] then
                -- super is native class
                assert(cls.__create == nil,
                    string.format("class() - create class \"%s\" with more than one creating function or native class",
                        classname));
                cls.__create = function() return super:create() end
            else
                -- super is pure lua class
                cls.__supers = cls.__supers or {}
                cls.__supers[#cls.__supers + 1] = super
                if not cls.super then
                    -- set first super pure lua class as class.super
                    cls.super = super
                end
            end
        else
            error(string.format("class() - create class \"%s\" with invalid super type",
                        classname), 0)
        end
    end

    cls.__index = cls
    if not cls.__supers or #cls.__supers == 1 then
        setmetatable(cls, {__index = cls.super})
    else
        setmetatable(cls, {__index = function(_, key)
            local supers = cls.__supers
            for i = 1, #supers do
                local super = supers[i]
                if super[key] then return super[key] end
            end
        end})
    end

    if not cls.ctor then
        -- add default constructor
        cls.ctor = function() end
    end
    cls.new = function(...)
        local instance
        if cls.__create then
            instance = cls.__create(...)
        else
            instance = {}
        end
        setmetatableindex(instance, cls)
        instance.class = cls
        instance:ctor(...)
        return instance
    end
    cls.create = function(_, ...)
        return cls.new(...)
    end

    return cls
end

local iskindof_
iskindof_ = function(cls, name)
    local __index = rawget(cls, "__index")
    if type(__index) == "table" and rawget(__index, "__cname") == name then return true end

    if rawget(cls, "__cname") == name then return true end
    local __supers = rawget(__index, "__supers")
    if not __supers then return false end
    for _, super in ipairs(__supers) do
        if iskindof_(super, name) then return true end
    end
    return false
end

function iskindof(obj, classname)
    local t = type(obj)
    if t ~= "table" and t ~= "userdata" then return false end

    local mt
    if t == "userdata" then
        if tolua.iskindof(obj, classname) then return true end
        mt = getmetatable(tolua.getpeer(obj))
    else
        mt = getmetatable(obj)
    end
    if mt then
        return iskindof_(mt, classname)
    end
    return false
end

function import(moduleName, currentModuleName)
    local currentModuleNameParts
    local moduleFullName = moduleName
    local offset = 1

    while true do
        if string.byte(moduleName, offset) ~= 46 then -- .
            moduleFullName = string.sub(moduleName, offset)
            if currentModuleNameParts and #currentModuleNameParts > 0 then
                moduleFullName = table.concat(currentModuleNameParts, ".") .. "." .. moduleFullName
            end
            break
        end
        offset = offset + 1

        if not currentModuleNameParts then
            if not currentModuleName then
                local n,v = debug.getlocal(3, 1)
                currentModuleName = v
            end

            currentModuleNameParts = string.split(currentModuleName, ".")
        end
        table.remove(currentModuleNameParts, #currentModuleNameParts)
    end

    return require(moduleFullName)
end

function handler(obj, method)
    return function(...)
        return method(obj, ...)
    end
end

function math.newrandomseed()
    local ok, socket = pcall(function()
        return require("socket")
    end)

    if ok then
        math.randomseed(tostring(socket.gettime()):reverse():sub(1, 6))
    else
        math.randomseed(os.time())
    end
    math.random()
    math.random()
    math.random()
    math.random()
end

function math.round(value)
    value = checknumber(value)
    return math.floor(value + 0.5)
end

--- nNum 源数字
--- n 小数位数
function math.GetPreciseDecimal(nNum, n)
	if type(nNum) ~= "number" then
		return nNum;
	end
	n = n or 0;
	n = math.floor(n)
	if n < 0 then
		n = 0;
	end
	local nDecimal = 10 ^ n
	local nTemp = math.floor(nNum * nDecimal);
	local nRet = nTemp / nDecimal;
	return nRet;
end

local pi_div_180 = math.pi / 180
function math.angle2radian(angle)
    return angle * pi_div_180
end

function math.radian2angle(radian)
    return radian * 180 / math.pi
end

function io.exists(path)
    local file = io.open(path, "r")
    if file then
        io.close(file)
        return true
    end
    return false
end

function io.readfile(path)
    local file = io.open(path, "r")
    if file then
        local content = file:read("*a")
        io.close(file)
        return content
    end
    return nil
end

function io.writefile(path, content, mode)
    mode = mode or "w+b"
    local file = io.open(path, mode)
    if file then
        if file:write(content) == nil then return false end
        io.close(file)
        return true
    else
        return false
    end
end

function io.pathinfo(path)
    local pos = string.len(path)
    local extpos = pos + 1
    while pos > 0 do
        local b = string.byte(path, pos)
        if b == 46 then -- 46 = char "."
            extpos = pos
        elseif b == 47 then -- 47 = char "/"
            break
        end
        pos = pos - 1
    end

    local dirname = string.sub(path, 1, pos)
    local filename = string.sub(path, pos + 1)
    extpos = extpos - pos
    local basename = string.sub(filename, 1, extpos - 1)
    local extname = string.sub(filename, extpos)
    return {
        dirname = dirname,
        filename = filename,
        basename = basename,
        extname = extname
    }
end

function io.filesize(path)
    local size = false
    local file = io.open(path, "r")
    if file then
        local current = file:seek()
        size = file:seek("end")
        file:seek("set", current)
        io.close(file)
    end
    return size
end

function table.nums(t)
    local count = 0
    if t then
        for k, v in pairs(t) do
			if v then
				count = count + 1
			end
        end
    end
    return count
end

function table.last(t)
	local last=false
	for k, v in pairs(t) do
		last=v
	end
    return last
end

function table.keys(hashtable)
    local keys = {}
    for k, v in pairs(hashtable) do
        keys[#keys + 1] = k
    end
    return keys
end

function table.values(hashtable)
    local values = {}
    for k, v in pairs(hashtable) do
        values[#values + 1] = v
    end
    return values
end

function table.sortAZ(source,k)
	table.sort(source,function (a,b)
			return string.byte(a[k],1)<string.byte(b[k],1)
		end)
end

function table.sortZA(source,k)
	table.sort(source,function (a,b)
			return string.byte(a[k],1)>string.byte(b[k],1)
		end)
end

function table.merge(dest, src)
    for k, v in pairs(src) do
        dest[k] = v
    end
end

function table.insertto(dest, src, begin)
    begin = checkint(begin)
    if begin <= 0 then
        begin = #dest + 1
    end

    local len = #src
    for i = 0, len - 1 do
        dest[i + begin] = src[i + 1]
    end
end

function table.contains(array, value,key)
	if array==nil then
		array={}
	end
    for k, v in pairs(array) do 
		if key~=nil then
			if v[key]==value[key] then
				return true
			end			
		elseif v == value then 
			return true 
		end 		
	end
    return false
end
-- 合并数组
function table.addRange(sourceTable, addTable)
	for k, v in pairs(addTable) do
		table.insert(sourceTable, v)
	end
end

function table.addValue(dest, val)
    for _, v in ipairs(dest) do
        if v == val then
            return
        end
    end
    table.insert(dest, val)
end

function table.getValue(dest, keyname, key)
    for _, v in ipairs(dest) do
        if v[keyname] == key then
            return v
        end
    end
    return nil
end

function table.append(t1, t2)
    for _, v in ipairs(t2) do
        table.insert(t1, v)
    end
    return t1
end

function table.merge_list(dest, src)
    local ret = {}
    for _, v in ipairs(dest) do
        table.insert(ret, v)
    end
    for _, v in ipairs(src) do
        table.insert(ret, v)
    end
    return ret
end

function table.indexof(array, value, begin)
    for i = begin or 1, #array do
        if array[i] == value then return i end
    end
    return -1
end

function table.keyof(hashtable, value)
    for k, v in pairs(hashtable) do
        if v == value then return k end
    end
    return nil
end

function table.removebyvalue(array, value, removeall)
    local c, i, max = 0, 1, #array
    while i <= max do
        if array[i] == value then
            table.remove(array, i)
            c = c + 1
            i = i - 1
            max = max - 1
            if not removeall then break end
        end
        i = i + 1
    end
    return c
end

function table.map(t, fn)
    for k, v in pairs(t) do
        t[k] = fn(v, k)
    end
end

function table.walk(t, fn)
    for k,v in pairs(t) do
        fn(v, k)
    end
end

function table.filter(t, fn)
    for k, v in pairs(t) do
        if not fn(v, k) then t[k] = nil end
    end
end

function table.unique(t, bArray)
    local check = {}
    local n = {}
    local idx = 1
    for k, v in pairs(t) do
        if not check[v] then
            if bArray then
                n[idx] = v
                idx = idx + 1
            else
                n[k] = v
            end
            check[v] = true
        end
    end
    return n
end

--比较两个table值是否一样
function table.equalvalue(t1, t2)
    if type(t1) ~= "table" or type(t2) ~= "table" then
        return t1 == t2
    end
    for k, v in pairs(t1) do
        if not table.equalvalue(t2[k], v) then
            return false
        end
    end
    for k, v in pairs(t2) do
        if not table.equalvalue(t1[k], v) then
            return false
        end
    end
    return true
end

-- 整型 key 的 map 转化为 list
function table.intMapToList(map)
    if not map then return nil end
	local rets = {}
	for k, v in pairs(map) do
		table.insert(rets, k)
		table.insert(rets, v)
	end
	return rets
end

function table.listToIntMap(list)
    if not list then return nil end
	local rets = {}
	for i = 1, #list, 2 do
		rets[list[i]] = list[i + 1]
	end
	return rets
end


local __table_insert = table.insert
local _string_format = string.format

function table.Serialize(obj, name, newline, depth, filter)
    local space = newline and "    " or ""
    newline = newline and true
    depth = depth or 0
    if depth > 10 then
        return "..."
    end
    local tab = {}
    local tmp = string.rep(space, depth)

    if name then
        if name ~= filter then
            if type(name) == "number" then
                __table_insert(tab, _string_format("%s[%s] = ", tmp, name))
            else
                __table_insert(tab, _string_format("%s%s = ", tmp, tostring(name)))
            end
        end
    end

    if type(obj) == "table" then
        if name ~= filter then
            __table_insert(tab, string.format("{%s",(newline and "\n" or "")))
            for k, v in pairs(obj) do
                __table_insert(tab, table.Serialize(v, k, newline, depth + 1, filter))
                if k ~= filter then
                    __table_insert(tab, ",")
                    __table_insert(tab, (newline and "\n" or ""))
                end
            end
            __table_insert(tab, string.rep(space, depth))
            __table_insert(tab, "}")
        end
    elseif type(obj) == "number" then
        __table_insert(tab, obj)
    elseif type(obj) == "string" then
        __table_insert(tab, _string_format("%q", obj))
    elseif type(obj) == "boolean" then
        __table_insert(tab, (obj and "true" or "false"))
    elseif type(obj) == "function" then
        -- tmp = tmp .. tostring(obj)
        __table_insert(tab, tostring(obj))
    elseif type(obj) == "userdata" then
        __table_insert(tab, tostring(obj))
    else
        __table_insert(tab, "\"[")
        __table_insert(tab, _string_format("%s", tostring(obj)))
        __table_insert(tab, "]\"")
    end
    return table.concat(tab)
end

-- 打印Table  filter 过滤打印节点名
function table.Dump(obj, name, filter)
    name = name or ""
    filter = filter or "class"
    print(debug.traceback(table.Serialize(obj, "<color=#00ff00>" .. name .. "</color>", true, 0, filter), 2))
end

function table.shuffle(tbr)
    for k, _ in ipairs(tbr) do
        local i = math.random(#tbr)
        if i ~= k then
            tbr[k], tbr[i] = tbr[i], tbr[k]
        end
    end
    return tbr
end

string._htmlspecialchars_set = {}
string._htmlspecialchars_set["&"] = "&amp;"
string._htmlspecialchars_set["\""] = "&quot;"
string._htmlspecialchars_set["'"] = "&#039;"
string._htmlspecialchars_set["<"] = "&lt;"
string._htmlspecialchars_set[">"] = "&gt;"

function string.htmlspecialchars(input)
    for k, v in pairs(string._htmlspecialchars_set) do
        input = string.gsub(input, k, v)
    end
    return input
end

function string.restorehtmlspecialchars(input)
    for k, v in pairs(string._htmlspecialchars_set) do
        input = string.gsub(input, v, k)
    end
    return input
end

function string.nl2br(input)
    return string.gsub(input, "\n", "<br />")
end

function string.text2html(input)
    input = string.gsub(input, "\t", "    ")
    input = string.htmlspecialchars(input)
    input = string.gsub(input, " ", "&nbsp;")
    input = string.nl2br(input)
    return input
end

function string.split(input, delimiter)
    input = tostring(input)
    delimiter = tostring(delimiter)
    if (delimiter=='') then return false end
    local pos,arr = 0, {}
    -- for each divider found
    for st,sp in function() return string.find(input, delimiter, pos, true) end do
        table.insert(arr, string.sub(input, pos, st - 1))
        pos = sp + 1
    end
    table.insert(arr, string.sub(input, pos))
    return arr
end

function string.ltrim(input)
    return string.gsub(input, "^[ \t\n\r]+", "")
end

function string.rtrim(input)
    return string.gsub(input, "[ \t\n\r]+$", "")
end

function string.trim(input)
    input = string.gsub(input, "^[ \t\n\r]+", "")
    return string.gsub(input, "[ \t\n\r]+$", "")
end

function string.ucfirst(input)
    return string.upper(string.sub(input, 1, 1)) .. string.sub(input, 2)
end

local function urlencodechar(char)
    return "%" .. string.format("%02X", string.byte(char))
end
function string.urlencode(input)
    -- convert line endings
    input = string.gsub(tostring(input), "\n", "\r\n")
    -- escape all characters but alphanumeric, '.' and '-'
    input = string.gsub(input, "([^%w%.%- ])", urlencodechar)
    -- convert spaces to "+" symbols
    return string.gsub(input, " ", "+")
end

function string.urldecode(input)
    input = string.gsub (input, "+", " ")
    input = string.gsub (input, "%%(%x%x)", function(h) return string.char(checknumber(h,16)) end)
    input = string.gsub (input, "\r\n", "\n")
    return input
end

function string.utf8len(input)
    local len  = string.len(input)
    local left = len
    local cnt  = 0
    local arr  = {0, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc}
    while left ~= 0 do
        local tmp = string.byte(input, -left)
        local i   = #arr
        while arr[i] do
            if tmp >= arr[i] then
                left = left - i
                break
            end
            i = i - 1
        end
        cnt = cnt + 1
    end
    return cnt
end

-- utf8 字符当两个长度计算
function string.utf8len2(input)
    local len  = string.len(input)
    local left = len
    local cnt  = 0
    local arr  = {0, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc}
    while left ~= 0 do
        local tmp = string.byte(input, -left)
        local i   = #arr
        while arr[i] do
            if tmp >= arr[i] then
                left = left - i
                break
            end
            i = i - 1
        end
        if i <= 1 then
            cnt = cnt + 1
        else
            cnt = cnt + 2
        end
    end
    return cnt
end

function string.formatnumberthousands(num)
    local formatted = tostring(checknumber(num))
    local k
    while true do
        formatted, k = string.gsub(formatted, "^(-?%d+)(%d%d%d)", '%1,%2')
        if k == 0 then break end
    end
    return formatted
end


function string.getBigNumStr(num)
	if num==nil then
		return num
	end
    local strLen=string.len(num)
    local bigNumStr=tostring(num)
    if strLen>4 and strLen<7 then
        bigNumStr= string.format("%0.1f",num/1000).."K"
    elseif  strLen>=7 and strLen<=10 then
        bigNumStr= string.format("%0.1f", num/1000000).."M"
    elseif  strLen> 10  then
        bigNumStr= string.format("%0.1f", num/1000000/1000).."B"
    end

    local pointIndex = string.find( bigNumStr, "." ,1, true)
    if not pointIndex then
        return string.formatnumberthousands(bigNumStr)
    else
        local front = string.sub(bigNumStr, 1, pointIndex -1)
        local tail = string.sub(bigNumStr, pointIndex + 1, string.len(bigNumStr))
        return string.format("%s.%s", string.formatnumberthousands(front), tail)
    end
    return bigNumStr
end

--判断utf8字符byte长度
function string.chsize( char )
	if not char then
		return 0
	elseif char > 240 then
		return 4
	elseif char > 225 then
		return 3
	elseif char > 192 then
		return 2
	else
		return 1
	end
end

--截取字符串，按字符截取
-- str:         要截取的字符串
-- startChar:   开始字符下标,从1开始
-- numChars:    要截取的字符长度
function string.utf8sub( str, startChar, numChars )
	local startIndex = 1
	while startChar > 1 do
		local char = string.byte(str, startIndex)
		startIndex = startIndex + string.chsize(char)
		startChar = startChar - 1
	end

	local currentIndex = startIndex

	while numChars > 0 and currentIndex <= #str do
		local char = string.byte(str, currentIndex)
		currentIndex = currentIndex + string.chsize(char)
		numChars = numChars -1
	end
	return str:sub(startIndex, currentIndex - 1), numChars
end


function string.getLongNameStr(name,limit)
	local subStr=name
	local charLen=CS.Utils.CalculatePlaces(subStr)
	if charLen>limit then
		subStr=string.utf8sub(subStr,1,limit-1).."."
	end
	return subStr
end

function string.cutLongStr(name,limit)
	local subStr=name
	local charLen=CS.Utils.CalculatePlaces(subStr)
	if charLen>limit then
		subStr=string.utf8sub(subStr,1,limit-1)
	end
	return subStr
end

-- 成功返回替换后的字符串，失败返回源字符串
string.replace = function(s, pattern, repl)
	local i,j = string.find(s, pattern, 1, true)
	if i and j then
		local ret = {}
		local start = 1
		while i and j do
			table.insert(ret, string.sub(s, start, i - 1))
			table.insert(ret, repl)
			start = j + 1
			i,j = string.find(s, pattern, start, true)
		end
		table.insert(ret, string.sub(s, start))
		return table.concat(ret)
	end
	return s
end

--避免json里面存整数key
function string.toJsonNumKey(index)
	local RcharIndex=index%(91-65)
	RcharIndex=RcharIndex+65
	local jsonIndex=string.char(RcharIndex)..index
	--print("转成了"..RcharIndex)
	return  jsonIndex
end

function string.compareVer(ver1,ver2)
	local ver1s= string.split(ver1,".")
	local ver2s= string.split(ver2,".")
	local isMax=false
	if ver1s[2]>ver2s[2] then
		isMax=true
	elseif ver1s[2]==ver2s[2] then
		isMax= ver1s[3]>ver2s[3]
	else
		isMax=false
	end
    return  isMax and 1 or 0
end

--function bee.isNull(uobj)
	--return uobj==nil or uobj:Equals(nil)
--end

--名字查找模糊匹配
function string.RegexName(str,matchStr)
	if str == "" or not str then
		return false
	end
	--local strTemp = string.match(str, "^[a-zA-Z0-9_\u4e00-\u9fa5]+$");

	local strTemp = string.match(string.lower(str),string.lower(matchStr))
	
	if strTemp == nil then
		return false;
	end
	return strTemp == string.lower(matchStr)
end

function string.IsNullOrEmpty(str)
	if str == "" or not str then
		return true
	end
end


function string.RichColorStr(str,colorStr)
	return "<color="..colorStr..">"..str.."</color>"
end

-- function string.widthSingle(inputstr)
--     -- 计算字符串宽度
--     -- 可以计算出字符宽度，用于显示使用
--    local lenInByte = #inputstr
--    local width = 0
--    local i = 1
--    while (i<=lenInByte) 
--     do
--         local curByte = string.byte(inputstr, i)
--         local byteCount = 1;
--         if curByte>0 and curByte<=127 then
--             byteCount = 1                                           --1字节字符
--         elseif curByte>=192 and curByte<223 then
--             byteCount = 2                                           --双字节字符
--         elseif curByte>=224 and curByte<239 then
--             byteCount = 3                                           --汉字
--         elseif curByte>=240 and curByte<=247 then
--             byteCount = 4                                           --4字节字符
--         end

--         local char = string.sub(inputstr, i, i+byteCount-1)
--         print(char)                                                         

--         i = i + byteCount                                 -- 重置下一字节的索引
--         width = width + 1                                 -- 字符的个数（长度）
--     end
--     return width
-- end

