GMContent=
{
	{examples="#loginGuest 1", notes="游客登录（自定义账号）", cb = function(args)
		if not args or not args[1] then
			UiManager:showToast("请输入账号")
			return
		end
		PlayerModel:setLoginType(LOGIN_TYPE.GUEST)
		PlayerModel:setTestDeviceID(args[1])
		if not bee.isInStart() then
			PlayerModel:setNotAutoLogin(false)
			PlayerModel:setIsLogin(false)
			Net:sendReq("pb.UserLogoutREQ", {})
		else
			LoginModel:guestLoginTest(args[1])
		end
	end},
	{examples="#addGold 10000000", notes="增加金币", cb = function(args)
		local host = string.replace(UrlManager:getServerUrl(), "ws://", "")
		local url = "http://" .. string.split(host, ":")[1] .. ":8005" .. "/?"
		url = url .. "cmd=add_coin" .. "&handler=game_helper" .. "&luaservice=1" .. "&response=1"
		url = url .. "&uid=" .. PlayerModel:getUid() .. "&coin=" .. tonumber(args[1]) .. "&flow_type=console" .. "&flow_attach=console"
		Net:getUrl(url)
	end},
	{examples="#addItem 10900001 1", notes="增加道具(id,数量)", cb = function(args)
		if not args or #args[1] < 2 then
			UiManager:showToast("参数错误")
			return
		end
		if not tpl_props[tonumber(args[1])] then
			UiManager:showToast("道具 id 不存在")
			return
		end
		local host = string.replace(UrlManager:getServerUrl(), "ws://", "")
		local url = "http://" .. string.split(host, ":")[1] .. ":8005/itemsvr/GM_add_item"
		Net:postUrl(url, {
			response = 1,
			uid = PlayerModel:getUid(),
			item_list = {
				{id = tonumber(args[1]), num = tonumber(args[2])}
			},
			flow_type = "gm",
			flow_attach = "gm",
		})
	end},
	{examples="#addRole 1001", notes="添加角色 id", cb = function(args)
		if not args or #args[1] < 1 then
			UiManager:showToast("参数错误")
			return
		end
		if not tpl_character[tonumber(args[1])] then
			UiManager:showToast("角色 id 不存在")
			return
		end
		local host = string.replace(UrlManager:getServerUrl(), "ws://", "")
		local url = "http://" .. string.split(host, ":")[1] .. ":8005/itemsvr/GM_unlock_role"
		Net:postUrl(url, {
			response = 1,
			uid = PlayerModel:getUid(),
			role_id = tonumber(args[1]),
			flow_type = "gm",
			flow_attach = "gm",
		})
	end},
	{examples="#addSkin " .. tpl_character_skin_list[2].id, notes="添加皮肤 皮肤id", cb = function(args)
		if not args or #args[1] < 1 then
			UiManager:showToast("参数错误")
			return
		end
		local d = tpl_character_skin[tonumber(args[1])]
		if not d then
			UiManager:showToast("皮肤 id 不存在")
			return
		end
		local host = string.replace(UrlManager:getServerUrl(), "ws://", "")
		local url = "http://" .. string.split(host, ":")[1] .. ":8005/itemsvr/GM_unlock_skin"
		Net:postUrl(url, {
			response = 1,
			uid = PlayerModel:getUid(),
			role_id = d.role,
			skin_id = d.id,
			flow_type = "gm",
			flow_attach = "gm",
		})
	end},
	{examples="#setPayUser " .. 1, notes="是否为付费用户(抽卡用) 1", cb = function(args)
		if not args or #args[1] < 1 then
			PlayerModel:setPayUser(0)
			return
		end
		PlayerModel:setPayUser(args[1])
	end},
	{examples="#betAction 7 1000", notes="Bet行动(type,chips)", cb = function(args)
		if not args or #args < 2 then
			return
		end
		Net:sendReq("pb.ActionREQ", {action_type = tonumber(args[1]), chips = tonumber(args[2])})
	end},
	{examples="#invitePlay 0000", notes="好友房邀请(uid)", cb = function(args)
		if not args or #args < 1 then
			return
		end
		Net:sendReq("pb.InvitePlayREQ", {to_uid = tonumber(args[1])})
	end},
	{examples="#openAllin " .. os.date("%Y%m%d%H%M", os.time()) .. " " .. (os.date("%Y%m%d%H%M", os.time() + 3600)), notes="Allin开启时间(开始时间 结束时间)", cb = function(args)
		if not args or #args < 2 then
			return
		end
		local st, et = args[1], args[2]
		local st1 = os.time({day=tonumber(string.sub(st, 7, 8)), month=tonumber(string.sub(st, 5, 6)), year=tonumber(string.sub(st, 1, 4)), hour=tonumber(string.sub(st, 9, 10)), min=tonumber(string.sub(st, 11, 12)), sec=0})
		local et1 = os.time({day=tonumber(string.sub(et, 7, 8)), month=tonumber(string.sub(et, 5, 6)), year=tonumber(string.sub(et, 1, 4)), hour=tonumber(string.sub(et, 9, 10)), min=tonumber(string.sub(et, 11, 12)), sec=0})
		local host = string.replace(UrlManager:getServerUrl(), "ws://", "")
		local url = "http://" .. string.split(host, ":")[1] .. ":8005/lobby/GM_update_allin_game_time"
		Net:postUrl(url, {
			response = 1,
			start_time = st1,
			end_time = et1,
		})
		return false
	end},
	{examples="#newerGuide 1010", notes="新手引导(引导id 0重置 -1跳过)", cb = function(args)
		if not args or #args < 1 then
			return
		end
		UiManager:hideUI("GameGuide")
		UiManager:hideUI("Story")
		GuideManager:setCurGuide(nil)
		if tonumber(args[1]) == 0 then
    		Net:sendReq("pb.SetNewerGuideStepREQ", {step = 0})
		elseif tonumber(args[1]) == -1 then
			local guide = 0
			for _, v in ipairs(tpl_guide_list) do
				if v.guide_type == 1 then
					guide = v.guide
				end
			end
			Net:sendReq("pb.SetNewerGuideStepREQ", {step = guide})
		else
			print("==== gggggggggg", args[1], 1001 == tonumber(args[1]))
			if 1001 == tonumber(args[1]) then
				CharacterModel:setGetroleguide()
			else
				GuideManager:startGuide(tonumber(args[1]))
			end
		end
	end},
	{examples="#testAppReview", notes="测试应用评分", cb = function(args)
		SdkHelper:startAppReview()
	end},
	{examples="#vibrate2 10,10,10 255,0,255",notes="手机震动2 时长,时长 强度,强度", cb = function(args)
		SdkHelper:vibrate2(args[1], args[2])
		local sys = CS.SdkHelper.getBrand()
		local model = CS.SdkHelper.getModel()
    	print("[VibrateManager] Operate Brand ==== ggg", sys, model)
	end},
	{examples="#showUI CommonNotice", notes="显示UI(ui名)", cb = function(args)
		UiManager:showUI(args[1])
	end},
	{examples="#fastScrap", notes="1BB爆衣", cb = function(args)
		tpl_constdata.ScrapBlindRate = 1
		tpl_constdata.ScrapRecoverBlindRate = 1
	end},
	-- {examples="#showAndroidInfo path", notes="显示Android特征(系统文件名)", cb = function(args)
	-- 	print("CS.SdkHelper.getBrand: ", CS.SdkHelper.getBrand())
	-- 	print("CS.SdkHelper.getModel: ", CS.SdkHelper.getModel())
	-- 	print("CS.SdkHelper.getFingerprint: ", CS.SdkHelper.getFingerprint())
	-- 	print("CS.SdkHelper.getManufacturer: ", CS.SdkHelper.getManufacturer())
	-- 	print("CS.SdkHelper.getBoard: ", CS.SdkHelper.getBoard())
	-- 	print("CS.SdkHelper.getProduct: ", CS.SdkHelper.getProduct())
	-- 	print("CS.SdkHelper.getOs: ", CS.SdkHelper.getOs())
	-- 	print("CU.SystemInfo.operatingSystem: ", CU.SystemInfo.operatingSystem)
	-- 	print("CU.SystemInfo.deviceModel: ", CU.SystemInfo.deviceModel)
	-- 	if args[1] ~= "path" then
	-- 		print("CS.SdkHelper.isSysFileExist: ", tostring(CS.SdkHelper.isSysFileExist(args[1])))
	-- 	end
	-- end},
}
