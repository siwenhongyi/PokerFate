local P = class("EmailModel", BaseModel)

function P:ctor()
    self.saveData = {}

    P.super.ctor(self)

    self.MAIL_TYPE = {
        Normal = 0, -- 普通邮件
        Special = 1,    -- 特殊邮件
    }
    
    self.STATUS = {
        UserMailStatusUnread          = 0,  -- 未读
        UserMailStatusRead            = 1,  -- 已读
        UserMailStatusReadNotReceived = 2,  -- 已读未领取
        UserMailStatusReadReceived    = 3,  -- 已读已领取
    }

    self.PAGE_SIZE = 20

    -- 各类型邮件信息
    self._mailInfos = {
        [0] = {
            mail_type = 0,
            total = 0,
            unread_total = 0,
            del_total = 0,  -- 可删除数量
            item_total = 0,
            list = {},
        },
        [1] = {
            mail_type = 1,
            total = 0,
            unread_total = 0,
            del_total = 0,  -- 可删除数量
            item_total = 0,
            list = {},
        },
    }

    -- 邮件详情列表 id = data
    self._mail_details = {}

    -- 邮件的信息 id = data
    self._mail_infos = {}
end

function P:getInfo(mail_type)
    return self._mailInfos[mail_type]
end

function P:getDetail(id)
    return self._mail_details[id]
end

function P:getFromName(data)
    if data.role_id and data.role_id > 0 then
        local r = CharacterModel:getRole(data.role_id)
        if r then
            return r:getName()
        end
        local d = tpl_character[data.role_id]
        if d then
            return _T(d.name)
        end
    end
    if data.system_mail_id and data.system_mail_id > 0 then
        local d = tpl_system_mail[data.system_mail_id]
        if d and d.sender then
            return _T(d.sender)
        end
    end
    return data.sender_name or ""
end

function P:getEmailTitle(data)
    if data.system_mail_id and data.system_mail_id > 0 then
        local d = tpl_system_mail[data.system_mail_id]
        if d then
            if data.title and data.title ~= "" then
                local args = json.decode(data.title)
                for k, v in ipairs(args) do
                    if string.sub(v, 1, 1) == "{" then
                        local td = json.decode(v)
                        args[k] = td[LAN:getLanguage()] or ""
                    else
                        args[k] = _T(v)
                    end
                end
                return _F(d.title, unpack(args))
            else
                return _T(d.title)
            end
        end
    end
    return data.title
end

function P:getEamilContent(data)
    local ret = data.content
    if data.system_mail_id and data.system_mail_id > 0 then
        local d = tpl_system_mail[data.system_mail_id]
        if d then
            if data.content and data.content ~= "" then
                local args = json.decode(data.content)
                if data.system_mail_id == 4001 then
                    local p1, p2 = "", ""
                    local act = tpl_theme_activity[args[1]]
                    if act then
                        p1 = _T(act.name)
                    end
                    local d2 = tpl_props[args[2]]
                    if d2 then
                        p2 = _T(d2.name) .. " x" .. args[3]
                    end
                    ret = _F(d.main_text, p1, p2)
                elseif data.system_mail_id == 4002 then
                    local p1, p2, p3 = "", "", ""
                    local act = tpl_theme_activity[args[1]]
                    if act then
                        p1 = _T(act.name)
                    end
                    p2 = TimeHelp:getDateTimeStrM(tonumber(args[2]), "/")
                    local d2 = tpl_props[args[3]]
                    if d2 then
                        p3 = _T(d2.name)
                    end
                    ret = _F(d.main_text, p1, p2, p3)
                else
                    for k, v in ipairs(args) do
                        if string.sub(v, 1, 1) == "{" then
                            local td = json.decode(v)
                            args[k] = td[LAN:getLanguage()] or ""
                        elseif string.find(v, "time_") then
                            local n = tonumber(string.sub(v, 6))
                            if n then
                                args[k] = TimeHelp:getDateTimeStrM(tonumber(string.sub(v, 6)), "/")
                            else
                                args[k] = _T(v)
                            end
                        else
                            local n = tonumber(v)
                            if n and tonumber(n) == v then
                                if tpl_props[n] then
                                    args[k] = _T(tpl_props[n].name)
                                else
                                    args[k] = _T(v)
                                end
                            else
                                args[k] = _T(v)
                            end
                        end
                        -- args[k] = _T(v)
                    end
                    ret = _F(d.main_text, unpack(args))
                end
            else
                ret = _T(d.main_text)
            end
        end
    end
    if LanguageManager:getLanguage() ~= "en" then
        ret = string.gsub(ret, " ",  Config.NO_WRAP_SPACE)
    end
    return ret
end

function P:getRedCount(mail_type)
    return self._mailInfos[mail_type].unread_total + self._mailInfos[mail_type].item_total
end

function P:refreshReddot()
    RedManager:addTagWithNum(self._mailInfos[self.MAIL_TYPE.Normal].unread_total + self._mailInfos[self.MAIL_TYPE.Normal].item_total, RedTag.NormalNewEmail)
    RedManager:addTagWithNum(self._mailInfos[self.MAIL_TYPE.Special].unread_total + self._mailInfos[self.MAIL_TYPE.Special].item_total, RedTag.SpecialNewEmail)
end

function P:reqNextEmailList(mail_type, cb)
    local info = self._mailInfos[mail_type]
    if #info.list < info.total then
        self:reqEmailList(mail_type, #info.list, cb)
        return true
    end
    return false
end

function P:reqEmailList(mail_type, offset, cb, size)
    mail_type = mail_type or self.MAIL_TYPE.Normal
    if not offset then
        offset = #self._mailInfos[mail_type].info
    end
	Net:post("mail/list", {
        offset = offset,
        size = size or self.PAGE_SIZE,
        mail_type = mail_type,
        lang = LanguageManager:getLanguage(),
        immediately = true,
    }, function(data)
		if data.code ~= 0 then
			return
		end
        if self._curLan ~= LanguageManager:getLanguage() then
            self._mail_details = {}
        end
        self._curLan = LanguageManager:getLanguage()
        local info = self._mailInfos[mail_type]
		info.total = data.total or 0
        info.unread_total = data.unread_total or 0
        info.del_total = data.del_total or 0
        info.item_total = data.item_total or 0
        if 0 == offset then
            info.list = {}
        end
        if data.list then
            table.append(info.list, data.list)
            for _, v in ipairs(data.list) do
                self._mail_infos[v.id] = v
                v.mail_type = mail_type
            end
        end
        for k, v in ipairs(info.list) do
            v.index = k
        end

        if cb then
            cb(data, mail_type)
        end

        bee.emit(EventDef.evt_refreshEmailList, info)

        self:refreshReddot()
	end)
end

function P:reqEmailNum(cb)
	Net:post("mail/num", nil, function(data)
		if data.code ~= 0 then
			return
		end

        local info = self._mailInfos[self.MAIL_TYPE.Normal]
		info.total = data.normal.total
        info.unread_total = data.normal.unread_total
        info.del_total = data.normal.del_total
        info.item_total = data.normal.item_total

        info = self._mailInfos[self.MAIL_TYPE.Special]
		info.total = data.special.total
        info.unread_total = data.special.unread_total
        info.del_total = data.special.del_total
        info.item_total = data.special.item_total

        if cb then
            cb(data)
        end
        self:refreshReddot()
        bee.emit(EventDef.evt_refreshEmailNum)
	end)
end

function P:reqEmailDetail(id, cb)
    if self._mail_details[id] then
        if cb then
            cb(self._mail_details[id])
        end
        return
    end
    Net:post("mail/detail", {
        id = id,
        lang = LanguageManager:getLanguage(),
    }, function(data)
		if data.code ~= 0 then
			return
		end
        self._mail_details[id] = data.data
        local d = self._mail_infos[id]
        if d then
            if d.status == self.STATUS.UserMailStatusUnread then
                self._mailInfos[d.mail_type].unread_total = self._mailInfos[d.mail_type].unread_total - 1
                self:refreshReddot()
            end
            d.status = data.data.status
        end
        if cb then
            cb(data.data)
        end
        self:reqEmailNum()
    end)
end

-- 领取附件
function P:reqEamilAttach(id_arr, mail_type, all, cb)
    Net:post("mail/receive", {
        id_arr = id_arr,
        mail_type = mail_type,
        all = all,
    }, function(data)
		if data.code ~= 0 then
			return
		end
        local info = self._mailInfos[mail_type]
        if id_arr then
            for _, v in ipairs(id_arr) do
                local d = self._mail_infos[v]
                if d then
                    d.status = self.STATUS.UserMailStatusReadReceived
                end
                d = self._mail_details[v]
                if d then
                    d.status = self.STATUS.UserMailStatusReadReceived
                end
                info.item_total = info.item_total - 1
            end
        elseif all then
            for _, v in ipairs(info.list) do
                if v.has_item then
                    v.status = self.STATUS.UserMailStatusReadReceived
                    local d = self._mail_details[v.id]
                    if d and #d.item_list > 0 then
                        d.status = self.STATUS.UserMailStatusReadReceived
                    end
                end
            end
            info.item_total = 0
        end
        self:refreshReddot()
        if cb then
            cb(data)
        end
        self:reqEmailNum()
    end)
end

function P:reqDelEamil(id_arr, mail_type, all, cb)
    Net:post("mail/del", {
        id_arr = id_arr,
        mail_type = mail_type,
        all = all,
    }, function(data)
		if data.code ~= 0 then
			return
		end
        if all then
            -- self:reqEmailList(mail_type, 0, cb)
            if cb then
                cb()
            end
        else
            local removeData = nil
            local info = self._mailInfos[mail_type]
            for _, id in ipairs(id_arr) do
                for k, v in ipairs(info.list) do
                    if v.id == id then
                        table.remove(info.list, k)
                        removeData = v
                        info.total = info.total - 1
                        break
                    end
                end
                self._mail_infos[id] = nil
            end
            for k, v in ipairs(info.list) do
                v.index = k
            end
            if cb then
                cb(removeData, mail_type)
            end
        end
        self:reqEmailNum()
    end)
end

-- 收藏
function P:reqCollEamil(id_arr, cancel, cb)
    Net:post("mail/coll", {
        id_arr = id_arr,
        cancel = cancel,
    }, function(data)
		if data.code ~= 0 then
			return
		end
        for _, v in ipairs(id_arr) do
            local d = self._mail_infos[v]
            if d then
                d.coll_type = cancel and 0 or 1
            end
            d = self._mail_details[v]
            if d then
                d.coll_type = cancel and 0 or 1
            end
        end
        if cb then
            cb(data)
        end
        self:reqEmailNum()
    end)
end

return P