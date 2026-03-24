-- 消息定义枚举
-- 消息名固定以 evt_ 前缀
-- 协议响应消息默认为 evt_响应名
local P = {
	"evt_onApplicationFocus",
	"evt_onApplicationQuit",
	"evt_onApplicationPause",
	
	"evt_onActivityDestroy",
	"evt_onActivityResume",
	"evt_onActivityPause",

	"evt_serverTimeCrossDay",--跨天消息
	
	"evt_onAdjustId",--adjust获取成功返回
    -- 登录数据
	"evt_faceBookLogin",--fb登录
	"evt_doLogin",   --开始登录
	"evt_autoLogin",  --自动登录
	"evt_createAccount",--创建游客账号
	"evt_offLine_login",--离线登录
	"evt_login_success",--登录成功
	"evt_login_fail",	-- 登录失败
	"evt_refreshBindStove", -- 刷新绑定Stove状态
	
	"evt_lan_mod", --改变多语言

	-- 支付
	"evt_pay_sucess",	-- 支付成功

	-- 主界面
	"evt_backgroundBlur",		-- 背景模糊
	"evt_refreshTopInfo",		-- 刷新顶部信息
	"evt_refreshName",
	"evt_refreshAvatar",
	"evt_refreshLobbyRole",
	"evt_refreshLobbyScene",
	"evt_refreshLobbyMusic",
	"evt_uiBlur",		-- ui 模糊
	"evt_refreshSysunlock", -- 刷新系统解锁

	-- 人个信息面板
	"evt_refreshDeclaration",	-- 刷新个人宣言

	-- poker
	"evt_refreshBlind",		-- 刷新 blind
	"evt_hideUiWhenAction",	-- 执行动作时隐藏 ui, 参数传 isVisible
	"evt_refreshShowBB", 	-- 刷新显示大盲

	-- poker record
	"evt_recordRunAction",	-- 执行行动

	-- color game
	"evt_onBallBound",		-- color game 小球弹起

	-- 邮件
	"evt_refreshEmailNum",	-- 刷新数量
	"evt_refreshEmailList",	-- 邮件列表刷新

	-- 公告
	"evt_noticeRefresh",

	-- 物品
	"evt_item_refresh",		-- 物品发生变化

	-- 角色
	"evt_role_back_to_main", -- 返回角色主界面
	"evt_role_awakened_back_to_bonds", -- 觉醒界面返回角色养成界面
	"evt_role_role_red", -- 角色变化 role_id
	"evt_role_newrole_red", -- 新角色红点变化 role_id
	"evt_role_newskin_red", -- 新皮肤红点变化 skin_id
	"evt_role_awaken_red", -- 新觉醒红点变化 role_id

	-- 活动
	"evt_activity_get",  -- 活动数据获取成功 活动id
	"evt_activity_over", -- 活动结束 活动id

	-- vip
	"evt_vipLevelUp", -- vip等级提升

	-- 比赛
	"evt_sng_not_available", -- SNG比赛未开放
}

EventDef = {}
for _, v in ipairs(P) do
	EventDef[v] = v
end

-- end
