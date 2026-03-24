local P = {}
LanguageManager = P
LAN = P

function P:init()
    self.cur_language = ""
	self:initLanguage()
end

function P:initLanguage()
	self.cur_language = LocalStore:getStringForKey("LANGUAGE_SETTING")
	if self.cur_language == "" then
		local lan = CU.Application.systemLanguage:ToString()
		if lan == "ChineseSimplified" then
			self.cur_language = "zh"
		elseif string.find(lan, "Chinese") then
			self.cur_language = "tw"
		elseif string.find(lan, "Japanese") then
			self.cur_language = "jp"
		elseif string.find(lan, "Korean") then
			-- self.cur_language = "ko"
			self.cur_language = "en"
		else
			self.cur_language = "en"
		end
		-- if bee.isInTest then
		-- 	self.cur_language = "en"	-- 对外测试默认英语
		-- end
		LocalStore:setStringForKey("LANGUAGE_SETTING", self.cur_language)
	elseif not tpl_mult_language_list[1][self.cur_language] then
		self.cur_language = "en"
	end

	CS.SdkHelper.setLanguage(self.cur_language)

	-- if self.cur_language ~= "tw" then
		CS.I18Img.isNeedTranslate = true
	-- end
end

function P:setLanguage(language)
	if language ~= self.cur_language then
		self.cur_language = language
		if self.cur_language ~= "tw" then
			CS.I18Img.isNeedTranslate = true
		end
		LocalStore:setStringForKey("LANGUAGE_SETTING", language)
		bee.emit("evt_lan_mod")
		self:refreshLan(UiManager:getUiRoot())
		self:refreshLan(UiManager:getMainRoot())
		self:refreshLan(UiManager:getPopRoot())
		local UiCanvaPost = bee.find("UIRoot/UiCanvaPost")
		if UiCanvaPost then
			self:refreshLan(UiCanvaPost)
		end
		-- PlayerModel:updateLang()
		CS.SdkHelper.setLanguage(self.cur_language)
	end
end

function P:refreshLan(node, force)
	if node and (force or node.transform.childCount > 0) then
		node:BroadcastMessage("UpdateI18n", CU.SendMessageOptions.DontRequireReceiver)
	end
end

function P:getLanguage()
	return self.cur_language
end

function P:getString(key, lan)
	local data = tpl_mult_language[key]
	if lan then
		return data and data[lan] or tostring(key)
	end
	if data and data[self.cur_language] then
		if self.cur_language ~= "en" then
            local s =  string.gsub(data[self.cur_language], " ",  Config.NO_WRAP_SPACE)
			return s
		end
		return data[self.cur_language]
	end
	return tostring(key)
end

function P:formatString(key, ...)
	local s = P:getString(key)
	return string.format(s, ...)
end

function P:formatParamString(key, ...)
	local s = P:getString(key)
	local params = {...}
	for i, v in ipairs(params) do
		local pattern = string.format("{p%d}", i)
		s = string.gsub(s, pattern, v)
	end
	return s
end

function P:getImage(key)
	local data = tpl_mult_image_text[key]
	return data and data[self.cur_language] or tostring(key)
end

_T = function(...) return P:getString(...) end
_F = function(...) return P:formatParamString(...) end
_FS = function(...) return P:formatString(...) end
_I = function(...) return P:getImage(...) end

