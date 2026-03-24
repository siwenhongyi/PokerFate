-- 红点管理器，统一管理红点系统
local P = {
    TAG = "REDDOT_DATA",
}
RedManager = P

function P:init()
    -- self._data = LocalStore:getTableData(self.TAG) or {}
    self._data = {}
    self._nodes = {}
    self._texts = {}
    self._dirty = false

    self._hides = nil    -- 隐藏不计算的红点系统
end

function P:clearData()
    self._data = {}
    self._nodes = {}
    self._texts = {}
    self._dirty = false
    self._hides = nil
    LocalStore:deleteValueForKey(self.TAG)
end

-- 添加一个红点标记
function P:addTag(...)
    local args, tbr, flag = self:_getTag(...), self._data, false
    for _, v in ipairs(args) do
        if not tbr[v] then
            tbr[v] = {}
            flag = true
        end
        tbr = tbr[v]
    end
    if flag then
        self._dirty = true
        LocalStore:saveTableData(self.TAG, self._data)
        self:_notify(args)
    end
    return flag
end

function P:addTagWithNum(num, ...)
    if not num or num <= 0 then
        self:removeTag(...)
    else
        local args, tbr, flag = self:_getTag(...), self._data, false
        for _, v in ipairs(args) do
            flag = true
            if not tbr[v] then
                tbr[v] = {}
            end
            tbr = tbr[v]
        end
        if flag and tbr and tbr["__num__"] ~= num then
            tbr["__num__"] = num;
            self._dirty = true;
            LocalStore:saveTableData(self.TAG, self._data)
            self:_notify(args);
        end
    end
end

-- 删除一个红点标记
function P:removeTag(...)
    local args, tbr, tbrs = self:_getTag(...), self._data, {}
    for k, v in ipairs(args) do
        if not tbr[v] then
            return false
        end
        tbrs[#tbrs + 1] = tbr
        if k == #args then
            tbr[v] = nil
        else
            tbr = tbr[v]
        end
    end
    for i = #tbrs, 2, -1 do
        if self:_isEmpty(tbrs[i]) then
            tbrs[i - 1][args[i - 1]] = nil
        else
            break
        end
    end
    LocalStore:saveTableData(self.TAG, self._data)
    self:_notify(args)
    return true
end

function P:_isEmpty(tbr)
    for k, _ in pairs(tbr) do
        if k ~= "__num__" then
            return false;
        end
    end
    return true;
end

-- 是否有红点标志
function P:isTag(...)
    return self:_isTag(self:_getTag(...))
end

function P:_isTag(args)
    local tbr = self._data
    for _, v in ipairs(args) do
        if not tbr[v] or (self._hides and self._hides[v]) then
            return false
        end
        tbr = tbr[v]
    end
    if self._hides and not self:_isEmpty(tbr) then
        local flag = false
        for k, _ in pairs(tbr) do
            if not self._hides[k] then
                flag = true
                break
            end
        end
        if not flag then
            return false
        end
    end
    return #args > 0
end

function P:_getTag(...)
    local args = {...}
    for k, v in ipairs(args) do
        args[k] = RedTagLink[v] or tostring(v)
    end
    if #args > 1 then
        local ret = {}
        for _, v in ipairs(args) do
            if "table" == type(v) then
                for _, vv in ipairs(v) do
                    ret[#ret + 1] = vv
                end
            else
                ret[#ret + 1] = v
            end
        end
        return ret
    end
    if args[1] and "table" == type(args[1]) then
        return clone(args[1])
    end
    return args
end

function P:_getNum(args)
    local num = 0
    local tbr = self._data
    for _, v in ipairs(args) do
        if not tbr[v] then
            return 0
        end
        tbr = tbr[v]
    end
    num = self:__getNum(tbr)
    return num
end

function P:__getNum(tbr)
    local num = 0
    if self:_isEmpty(tbr) then
        num = num + (tbr["__num__"] or 1)
    else
        for k, v in pairs(tbr) do
            if k ~= "__num__" then
                num = num + self:__getNum(v)
            end
        end
    end
    return num
end

function P:_notify(args)
    local nulls = nil
    while #args > 0 do
        local tag = table.concat(args, "_")
        if self._nodes[tag] then
            local flag = self:_isTag(args)
            for _, v in ipairs(self._nodes[tag]) do
                if bee.isNull(v) then
                    if not nulls then
                        nulls = {v}
                    else
                        nulls[#nulls + 1] = v
                    end
                else
                    v:SetActive(flag)
                end
            end
        end
        if self._texts[tag] then
            local flag = self:_isTag(args)
            for _, v in ipairs(self._texts[tag]) do
                if bee.isNull(v) then
                    if not nulls then
                        nulls = {v}
                    else
                        nulls[#nulls + 1] = v
                    end
                else
                    -- v:SetActive(flag)
                    bee.setText(v, self:_getNum(args))
                end
            end
        end
        table.remove(args, #args)
    end
    if nulls then
        for _, v in ipairs(nulls) do
            self:unbind(v)
        end
        if bee.isEditor then
            print("RedManager ERROR: notify null object", json.encode(args), debug.traceback())
        end
    end
end

-- 绑定物体到红点标志上
function P:bind(go, ...)
    if bee.isNull(go) then
        return
    end
    local args = self:_getTag(...)
    local tag = table.concat(args, "_")
    self._nodes[go] = tag
    if not self._nodes[tag] then
        self._nodes[tag] = {go}
    else
        self._nodes[tag][#self._nodes[tag] + 1] = go
    end
    go:SetActive(self:_isTag(args))
end

-- 绑定给点和数字
function P:bindWithText(go, text, ...)
    self:bind(go, ...)
    self:bindText(text, ...)
end

function P:bindText(text, ...)
    if bee.isNull(text) then
        return
    end
    local args = self:_getTag(...)
    local tag = table.concat(args, "_")
    self._texts[text] = tag
    if not self._texts[tag] then
        self._texts[tag] = {text}
    else
        self._texts[tag][#self._texts[tag] + 1] = text
    end
    bee.setText(text, self:_getNum(args))
end

-- 取消绑定物体
function P:unbind(go, text)
    if go then
        local tag = self._nodes[go]
        self._nodes[go] = nil
        if tag and self._nodes[tag] then
            for k, v in ipairs(self._nodes[tag]) do
                if v == go then
                    table.remove(self._nodes[tag], k)
                    break
                end
            end
        end
    end
    if text then
        local tag = self._texts[text]
        self._texts[text] = nil
        if tag and self._texts[tag] then
            for k, v in ipairs(self._texts[tag]) do
                if v == text then
                    table.remove(self._texts[tag], k)
                    break
                end
            end
        end
    end
end

function P:hideTag(tag, isHide)
    if not tag then return end

    if isHide then
        if not self._hides then
            self._hides = {}
        end
        self._hides[tag] = true
    else
        if self._hides then
            self._hides[tag] = nil
            if not next(self._hides) then
                self._hides = nil
            end
        end
    end
    local args = self:_getTag(tag)
    self:_notify(args)
end

